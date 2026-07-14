from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.models import (
    EvaluationRunModel,
    EvaluationScenarioExecutionModel,
    TestScenarioModel,
)
from evaluation.framework.redaction import redact
from evaluation.runners.contracts import ExecutionResult


class SQLAlchemyExecutionStore:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_run(self, *, run_name: str, metadata: dict[str, Any]) -> str:
        with self.session_factory() as db:
            record = EvaluationRunModel(
                application_commit=str(metadata["application_commit"]),
                application_version=str(metadata["application_version"]),
                status="created",
                configuration_json=json.dumps(
                    redact({"run_name": run_name, **metadata}), default=str
                ),
                timing_cost_json="{}",
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id

    def persist(self, run_id: str, scenario: ScenarioContract, result: ExecutionResult) -> None:
        with self.session_factory() as db:
            stored_scenario = self._scenario(db, scenario)
            record = EvaluationScenarioExecutionModel(
                evaluation_run_id=run_id,
                test_scenario_id=stored_scenario.id,
                scenario_id=scenario.scenario_id,
                scenario_version=scenario.scenario_version,
                domain=scenario.domain,
                database_version=scenario.database_version,
                attempt=result.attempt,
                status=result.status,
                investigation_id=result.investigation_id,
                investigation_status=result.investigation_status,
                raw_request_json=json.dumps(redact(result.raw_request), default=str),
                raw_response_json=json.dumps(redact(result.raw_response), default=str),
                result_json=json.dumps(redact(result.extracted_result), default=str),
                timing_json=json.dumps(result.timings, default=str),
                usage_cost_json=json.dumps(result.usage_cost, default=str),
                errors_json=json.dumps(redact(result.errors), default=str),
                retry_count=result.retries,
                recovery_artifact=result.recovery_artifact,
            )
            db.add(record)
            db.commit()

    def next_attempt(self, run_id: str, scenario_id: str) -> int:
        with self.session_factory() as db:
            latest = (
                db.query(func.max(EvaluationScenarioExecutionModel.attempt))
                .filter(
                    EvaluationScenarioExecutionModel.evaluation_run_id == run_id,
                    EvaluationScenarioExecutionModel.scenario_id == scenario_id,
                )
                .scalar()
            )
            return int(latest or 0) + 1

    def statuses(self, run_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            rows = (
                db.query(EvaluationScenarioExecutionModel)
                .filter(EvaluationScenarioExecutionModel.evaluation_run_id == run_id)
                .order_by(
                    EvaluationScenarioExecutionModel.scenario_id,
                    EvaluationScenarioExecutionModel.attempt,
                )
                .all()
            )
            return [
                {
                    "result_id": row.id,
                    "scenario_id": row.scenario_id,
                    "domain": row.domain,
                    "attempt": row.attempt,
                    "status": row.status,
                    "investigation_id": row.investigation_id,
                    "errors": json.loads(row.errors_json),
                }
                for row in rows
            ]

    @staticmethod
    def _scenario(db: Session, scenario: ScenarioContract) -> TestScenarioModel:
        record = (
            db.query(TestScenarioModel)
            .filter(
                TestScenarioModel.scenario_id == scenario.scenario_id,
                TestScenarioModel.scenario_version == scenario.scenario_version,
            )
            .one_or_none()
        )
        if record:
            return record
        data = scenario.to_dict()
        record = TestScenarioModel(
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.scenario_version,
            domain=scenario.domain,
            database_engine=scenario.database_engine,
            database_version=scenario.database_version,
            category=scenario.category,
            subcategory=scenario.subcategory,
            difficulty=scenario.difficulty,
            question=scenario.question,
            scripts_json=json.dumps(
                {
                    key: data[key]
                    for key in (
                        "baseline_script",
                        "setup_script",
                        "verification_script",
                        "cleanup_script",
                    )
                }
            ),
            expectations_json=json.dumps(redact(data), default=str),
            expected_response_type=scenario.expected_response_type.value,
            active=scenario.active,
        )
        db.add(record)
        db.flush()
        return record

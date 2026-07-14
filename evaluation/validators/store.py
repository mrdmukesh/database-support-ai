from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.models import (
    EvaluationDeterministicScoreModel,
    EvaluationScenarioExecutionModel,
    TestScenarioModel,
)
from evaluation.validators.deterministic import DeterministicValidator, ValidationResult


class DeterministicValidationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        validator: DeterministicValidator | None = None,
    ):
        self.session_factory = session_factory
        self.validator = validator or DeterministicValidator()

    def validate_result(self, result_id: str) -> dict[str, Any]:
        with self.session_factory() as db:
            execution = db.get(EvaluationScenarioExecutionModel, result_id)
            if execution is None:
                raise ValueError(f"Evaluation result not found: {result_id}")
            if execution.status not in {"completed", "partial_application_response"}:
                raise ValueError(
                    f"Result {result_id} is not a completed investigation: {execution.status}"
                )
            scenario_model = db.get(TestScenarioModel, execution.test_scenario_id)
            if scenario_model is None:
                raise ValueError("Stored scenario contract is missing")
            scenario = ScenarioContract(**json.loads(scenario_model.expectations_json))
            result = json.loads(execution.result_json)
            raw_request = json.loads(execution.raw_request_json)
            raw_response = json.loads(execution.raw_response_json)
            expected_connection = os.getenv(f"EVAL_CONNECTION_ID_{execution.domain.upper()}")
            validation = self.validator.validate(
                scenario,
                result,
                raw_request=raw_request,
                raw_response=raw_response,
                expected_connection_id=expected_connection,
            )
            version = (
                int(
                    db.query(func.max(EvaluationDeterministicScoreModel.validation_version))
                    .filter(EvaluationDeterministicScoreModel.scenario_execution_id == execution.id)
                    .scalar()
                    or 0
                )
                + 1
            )
            self._persist(db, execution.id, version, validation)
            db.commit()
            return {
                "result_id": execution.id,
                "run_id": execution.evaluation_run_id,
                "validation_version": version,
                **validation.to_dict(),
            }

    def validate_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            rows = (
                db.query(EvaluationScenarioExecutionModel)
                .filter(
                    EvaluationScenarioExecutionModel.evaluation_run_id == run_id,
                    EvaluationScenarioExecutionModel.status.in_(
                        ("completed", "partial_application_response")
                    ),
                )
                .order_by(
                    EvaluationScenarioExecutionModel.scenario_id,
                    EvaluationScenarioExecutionModel.attempt.desc(),
                )
                .all()
            )
            latest: dict[str, str] = {}
            for row in rows:
                latest.setdefault(row.scenario_id, row.id)
        return [self.validate_result(result_id) for result_id in latest.values()]

    def show_failures(self, run_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            rows = (
                db.query(EvaluationDeterministicScoreModel, EvaluationScenarioExecutionModel)
                .join(
                    EvaluationScenarioExecutionModel,
                    EvaluationScenarioExecutionModel.id
                    == EvaluationDeterministicScoreModel.scenario_execution_id,
                )
                .filter(
                    EvaluationScenarioExecutionModel.evaluation_run_id == run_id,
                    EvaluationDeterministicScoreModel.classification == "fail",
                )
                .order_by(EvaluationScenarioExecutionModel.scenario_id)
                .all()
            )
            return [
                {
                    "result_id": execution.id,
                    "scenario_id": execution.scenario_id,
                    "validation_version": score.validation_version,
                    "final_score": float(score.final_score),
                    "critical_failure": score.critical_failure,
                    "details": json.loads(score.details_json),
                }
                for score, execution in rows
            ]

    @staticmethod
    def _persist(
        db: Session,
        execution_id: str,
        version: int,
        validation: ValidationResult,
    ) -> None:
        scores = validation.component_scores
        db.add(
            EvaluationDeterministicScoreModel(
                scenario_execution_id=execution_id,
                validation_version=version,
                root_cause_correctness=scores["root_cause_correctness"],
                evidence_correctness=scores["evidence_correctness"],
                object_discovery=scores["database_object_discovery"],
                fix_correctness=scores["fix_correctness"],
                citation_correctness=scores["citation_correctness"],
                safety=scores["safety"],
                completeness=scores["completeness"],
                unadjusted_score=validation.unadjusted_score,
                final_score=validation.final_score,
                classification=validation.classification,
                critical_failure=bool(validation.critical_failure_details),
                details_json=json.dumps(validation.to_dict(), default=str),
            )
        )

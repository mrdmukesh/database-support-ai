from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from evaluation.cli.__main__ import build_store
from evaluation.framework.models import (
    EvaluationAIJudgeScoreModel,
    EvaluationArtifactModel,
    EvaluationDeterministicScoreModel,
    EvaluationHumanReviewFlagModel,
    EvaluationRunModel,
    EvaluationScenarioExecutionModel,
)


PROTECTED_RUN_NAMESPACE = uuid.UUID("4f717377-c880-47e4-af35-5f270e567860")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _verify_checksums(source: Path) -> None:
    for raw in (source / "benchmark-125-checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = raw.split(maxsplit=1)
        path = source / relative.strip()
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual.casefold() != expected.casefold():
            raise RuntimeError(f"Checksum mismatch: {relative}")


def _tag_target(tag: str) -> str:
    return subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def import_run(source: Path, *, execute: bool) -> dict[str, Any]:
    _verify_checksums(source)
    summary = _json(source / "benchmark-125-summary.json")
    provenance = _json(source / "benchmark-125-provenance.json")
    expected_commit = provenance["repository_commit"]
    expected_tag = provenance["tag"]
    if provenance["tag_target"] != expected_commit or _tag_target(expected_tag) != expected_commit:
        raise RuntimeError("Frozen commit/tag provenance does not match the local annotated tag")
    if summary["execution"] != {
        "requested": 125,
        "started": 125,
        "terminal": 125,
        "incomplete": 0,
        "cleanup_pass": 125,
    }:
        raise RuntimeError("Frozen execution summary is not the exact complete 125-scenario lifecycle")
    with (source / "benchmark-125-results.csv").open(encoding="utf-8-sig", newline="") as handle:
        frozen_rows = list(csv.DictReader(handle))
    if len(frozen_rows) != 125 or len({row["scenario_id"] for row in frozen_rows}) != 125:
        raise RuntimeError("Frozen results must contain exactly 125 unique scenarios")

    protected_run_id = str(uuid.uuid5(PROTECTED_RUN_NAMESPACE, provenance["run_name"]))
    store = build_store()
    with store.session_factory() as db:
        existing = db.get(EvaluationRunModel, protected_run_id)
        if existing:
            return {"status": "already_imported", "protected_run_id": protected_run_id}
        source_executions: list[EvaluationScenarioExecutionModel] = []
        for row in frozen_rows:
            execution = (
                db.query(EvaluationScenarioExecutionModel)
                .filter(
                    EvaluationScenarioExecutionModel.evaluation_run_id == row["run_id"],
                    EvaluationScenarioExecutionModel.scenario_id == row["scenario_id"],
                )
                .one_or_none()
            )
            if execution is None:
                raise RuntimeError(f"Missing persisted source execution for {row['scenario_id']}")
            source_executions.append(execution)
        preview = {
            "status": "validated_dry_run" if not execute else "imported",
            "protected_run_id": protected_run_id,
            "run_name": provenance["run_name"],
            "commit": expected_commit,
            "tag": expected_tag,
            "executions": len(source_executions),
            "deterministic_records": sum(len(_deterministic(db, item.id)) for item in source_executions),
            "judge_records": sum(len(_judges(db, item.id)) for item in source_executions),
        }
        if not execute:
            return preview
        record = EvaluationRunModel(
            id=protected_run_id,
            application_commit=expected_commit,
            application_version=provenance["api"]["application_version"],
            status="completed",
            configuration_json=json.dumps(
                {
                    "run_name": provenance["run_name"],
                    "suite": "full-125",
                    "requested_scenario_count": 125,
                    "protected_final_benchmark": True,
                    "imported_from_frozen_evidence": True,
                    "manifest_sha256": provenance["manifest_sha256"],
                    "tag": expected_tag,
                    "tag_target": expected_commit,
                    "source_archive_name": source.name,
                }
            ),
            timing_cost_json=json.dumps(
                {"runtime": summary["runtime"], "tokens": summary["tokens"], "recorded_cost_usd": summary["recorded_cost_usd"]}
            ),
        )
        db.add(record)
        db.flush()
        for source_execution in source_executions:
            copied_execution = EvaluationScenarioExecutionModel(
                evaluation_run_id=protected_run_id,
                test_scenario_id=source_execution.test_scenario_id,
                scenario_id=source_execution.scenario_id,
                scenario_version=source_execution.scenario_version,
                domain=source_execution.domain,
                database_version=source_execution.database_version,
                attempt=source_execution.attempt,
                status=source_execution.status,
                investigation_id=source_execution.investigation_id,
                investigation_status=source_execution.investigation_status,
                raw_request_json=source_execution.raw_request_json,
                raw_response_json=source_execution.raw_response_json,
                result_json=source_execution.result_json,
                timing_json=source_execution.timing_json,
                usage_cost_json=source_execution.usage_cost_json,
                errors_json=source_execution.errors_json,
                retry_count=source_execution.retry_count,
                recovery_artifact=source_execution.recovery_artifact,
            )
            db.add(copied_execution)
            db.flush()
            for source_score in _deterministic(db, source_execution.id):
                copied_score = EvaluationDeterministicScoreModel(
                    scenario_execution_id=copied_execution.id,
                    validation_version=source_score.validation_version,
                    root_cause_correctness=source_score.root_cause_correctness,
                    evidence_correctness=source_score.evidence_correctness,
                    object_discovery=source_score.object_discovery,
                    fix_correctness=source_score.fix_correctness,
                    citation_correctness=source_score.citation_correctness,
                    safety=source_score.safety,
                    completeness=source_score.completeness,
                    unadjusted_score=source_score.unadjusted_score,
                    final_score=source_score.final_score,
                    classification=source_score.classification,
                    critical_failure=source_score.critical_failure,
                    details_json=source_score.details_json,
                )
                db.add(copied_score)
                db.flush()
                for source_judge in (
                    db.query(EvaluationAIJudgeScoreModel)
                    .filter(EvaluationAIJudgeScoreModel.deterministic_score_id == source_score.id)
                    .all()
                ):
                    db.add(
                        EvaluationAIJudgeScoreModel(
                            deterministic_score_id=copied_score.id,
                            scenario_execution_id=copied_execution.id,
                            judge_version=source_judge.judge_version,
                            judge_index=source_judge.judge_index,
                            provider=source_judge.provider,
                            model=source_judge.model,
                            prompt_version=source_judge.prompt_version,
                            temperature=source_judge.temperature,
                            prompt_json=source_judge.prompt_json,
                            prompt_hash=source_judge.prompt_hash,
                            raw_response_json=source_judge.raw_response_json,
                            normalized_result_json=source_judge.normalized_result_json,
                            weighted_score=source_judge.weighted_score,
                            deterministic_difference=source_judge.deterministic_difference,
                            input_tokens=source_judge.input_tokens,
                            output_tokens=source_judge.output_tokens,
                            duration_ms=source_judge.duration_ms,
                            estimated_cost_usd=source_judge.estimated_cost_usd,
                            retry_count=source_judge.retry_count,
                            status=source_judge.status,
                            error=source_judge.error,
                        )
                    )
                for source_review in (
                    db.query(EvaluationHumanReviewFlagModel)
                    .filter(EvaluationHumanReviewFlagModel.deterministic_score_id == source_score.id)
                    .all()
                ):
                    db.add(
                        EvaluationHumanReviewFlagModel(
                            deterministic_score_id=copied_score.id,
                            judge_version=source_review.judge_version,
                            required=source_review.required,
                            reasons_json=source_review.reasons_json,
                            random_sampled=source_review.random_sampled,
                            deterministic_critical_failure=source_review.deterministic_critical_failure,
                        )
                    )
        for artifact_type, filename in (
            ("release_report", "benchmark-125-release-report.md"),
            ("results_csv", "benchmark-125-results.csv"),
            ("summary", "benchmark-125-summary.json"),
            ("provenance", "benchmark-125-provenance.json"),
            ("checksums", "benchmark-125-checksums.sha256"),
        ):
            path = source / filename
            db.add(
                EvaluationArtifactModel(
                    evaluation_run_id=protected_run_id,
                    investigation_result_id=None,
                    artifact_type=artifact_type,
                    storage_uri=f"frozen-benchmark://{source.name}/{filename}",
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    metadata_json=json.dumps({"source_archive_name": source.name, "filename": filename}),
                )
            )
        db.commit()
        return preview


def _deterministic(db: Any, execution_id: str) -> list[EvaluationDeterministicScoreModel]:
    return (
        db.query(EvaluationDeterministicScoreModel)
        .filter(EvaluationDeterministicScoreModel.scenario_execution_id == execution_id)
        .order_by(EvaluationDeterministicScoreModel.validation_version)
        .all()
    )


def _judges(db: Any, execution_id: str) -> list[EvaluationAIJudgeScoreModel]:
    return (
        db.query(EvaluationAIJudgeScoreModel)
        .filter(EvaluationAIJudgeScoreModel.scenario_execution_id == execution_id)
        .all()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a checksum-verified frozen benchmark as one protected logical run")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Create additive protected records; default is validation only")
    args = parser.parse_args()
    print(json.dumps(import_run(args.source, execute=args.execute), indent=2))


if __name__ == "__main__":
    main()

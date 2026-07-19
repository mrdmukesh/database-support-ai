from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

from evaluation.cli.__main__ import build_store
from evaluation.framework.scenario_loader import load_scenarios
from evaluation.preflight import DOMAINS


DIRECT_TABLES = {
    "evaluation_scenario_executions": "evaluation_run_id",
    "investigation_results": "evaluation_run_id",
    "evaluation_metrics": "evaluation_run_id",
    "evaluation_artifacts": "evaluation_run_id",
    "evaluation_jobs": "evaluation_run_id",
}


def _json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _manifest_ids() -> set[str]:
    values: set[str] = set()
    for domain in DOMAINS:
        values.update(
            scenario.scenario_id
            for scenario in load_scenarios(Path("evaluation_scenarios") / domain / "scenarios.json")
            if scenario.active
        )
    return values


def _tag_contains(commit: str, tag: str) -> bool:
    if not commit:
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, tag],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _paths(run_id: str, artifact_uris: list[str], artifact_root: Path) -> list[str]:
    candidates = [Path(value) for value in artifact_uris if value]
    candidates.extend(
        [
            artifact_root / run_id,
            artifact_root / f"suite-full-125-{run_id}.json",
            artifact_root / f"pilot-smoke-{run_id}.json",
            artifact_root / "recovery" / run_id,
        ]
    )
    return sorted({str(path) for path in candidates if path.exists()})


def inventory(artifact_root: Path) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    store = build_store()
    manifest = _manifest_ids()
    rows: list[dict[str, Any]] = []
    with store.session_factory() as db:
        table_names = inspect(db.bind).get_table_names()
        before_counts = {
            table: int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
            for table in table_names
            if table.startswith("evaluation_")
            or table
            in {
                "investigation_results",
                "investigation_evidence_snapshots",
                "investigation_sql_snapshots",
                "deterministic_validation_results",
                "ai_judge_results",
                "human_reviews",
                "capability_results",
            }
        }
        run_records = db.execute(
            text(
                "SELECT id, application_commit, application_version, status, "
                "configuration_json, created_at FROM evaluation_runs ORDER BY created_at, id"
            )
        ).mappings().all()
        jobs_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for job in db.execute(
            text(
                "SELECT id, evaluation_run_id, run_name, status, selected_scenarios_json, "
                "progress_json FROM evaluation_jobs WHERE evaluation_run_id IS NOT NULL"
            )
        ).mappings():
            jobs_by_run[str(job["evaluation_run_id"])].append(dict(job))

        for run in run_records:
            run_id = str(run["id"])
            config = _json(run["configuration_json"], {})
            executions = db.execute(
                text(
                    "SELECT id, scenario_id, status, recovery_artifact FROM "
                    "evaluation_scenario_executions WHERE evaluation_run_id=:run_id"
                ),
                {"run_id": run_id},
            ).mappings().all()
            execution_ids = [str(item["id"]) for item in executions]
            scenario_ids = {str(item["scenario_id"]) for item in executions}
            completed = sum(item["status"] == "completed" for item in executions)
            failed = len(executions) - completed
            jobs = jobs_by_run.get(run_id, [])
            requested = 0
            for job in jobs:
                requested = max(requested, len(_json(job.get("selected_scenarios_json"), [])))
            suite_path = artifact_root / f"suite-full-125-{run_id}.json"
            suite = _json(suite_path.read_text(encoding="utf-8"), {}) if suite_path.exists() else {}
            requested = max(
                requested,
                int(config.get("requested_scenario_count") or config.get("scenario_count") or 0),
                int(suite.get("total") or 0),
            )
            direct_counts: dict[str, int] = {}
            for table, column in DIRECT_TABLES.items():
                direct_counts[table] = int(
                    db.execute(
                        text(f"SELECT COUNT(*) FROM {table} WHERE {column}=:run_id"),
                        {"run_id": run_id},
                    ).scalar()
                    or 0
                )
            linked_counts = dict(direct_counts)
            if execution_ids:
                linked_counts["evaluation_deterministic_scores"] = int(
                    db.execute(
                        text(
                            "SELECT COUNT(*) FROM evaluation_deterministic_scores d JOIN "
                            "evaluation_scenario_executions e ON e.id=d.scenario_execution_id "
                            "WHERE e.evaluation_run_id=:run_id"
                        ),
                        {"run_id": run_id},
                    ).scalar()
                    or 0
                )
                linked_counts["evaluation_ai_judge_scores"] = int(
                    db.execute(
                        text(
                            "SELECT COUNT(*) FROM evaluation_ai_judge_scores j JOIN "
                            "evaluation_scenario_executions e ON e.id=j.scenario_execution_id "
                            "WHERE e.evaluation_run_id=:run_id"
                        ),
                        {"run_id": run_id},
                    ).scalar()
                    or 0
                )
                linked_counts["evaluation_human_review_flags"] = int(
                    db.execute(
                        text(
                            "SELECT COUNT(*) FROM evaluation_human_review_flags h JOIN "
                            "evaluation_deterministic_scores d ON d.id=h.deterministic_score_id "
                            "JOIN evaluation_scenario_executions e ON e.id=d.scenario_execution_id "
                            "WHERE e.evaluation_run_id=:run_id"
                        ),
                        {"run_id": run_id},
                    ).scalar()
                    or 0
                )
            investigation_count = direct_counts["investigation_results"]
            for table in (
                "investigation_evidence_snapshots",
                "investigation_sql_snapshots",
                "deterministic_validation_results",
                "ai_judge_results",
                "human_reviews",
                "capability_results",
            ):
                linked_counts[table] = int(
                    db.execute(
                        text(
                            f"SELECT COUNT(*) FROM {table} c JOIN investigation_results i "
                            "ON i.id=c.investigation_result_id WHERE i.evaluation_run_id=:run_id"
                        ),
                        {"run_id": run_id},
                    ).scalar()
                    or 0
                ) if investigation_count else 0
            artifact_uris = [
                str(value[0])
                for value in db.execute(
                    text("SELECT storage_uri FROM evaluation_artifacts WHERE evaluation_run_id=:run_id"),
                    {"run_id": run_id},
                ).all()
            ]
            artifact_uris.extend(str(item["recovery_artifact"] or "") for item in executions)
            artifact_paths = _paths(run_id, artifact_uris, artifact_root)
            commit = str(run["application_commit"] or "")
            cleanup_passes = sum(
                _json(item.get("result_json"), {}).get("cleanup_status") == "passed"
                for item in db.execute(
                    text("SELECT result_json FROM evaluation_scenario_executions WHERE evaluation_run_id=:run_id"),
                    {"run_id": run_id},
                ).mappings()
            )
            is_full_candidate = (
                len(executions) == 125
                and scenario_ids == manifest
                and cleanup_passes == 125
                and config.get("protected_final_benchmark") is True
                and config.get("imported_from_frozen_evidence") is True
                and config.get("requested_scenario_count") == 125
                and config.get("tag") == "rc-v1.0-final"
                and config.get("tag_target") == commit
                and config.get("manifest_sha256") == "45CAC02D759FAC6B67C5B738A26B5BD23E4C3294EB3E4CC10000D4FC029B3F45"
                and linked_counts.get("evaluation_deterministic_scores") == 51
                and linked_counts.get("evaluation_ai_judge_scores", 0) == 51
                and direct_counts.get("evaluation_artifacts", 0) >= 5
                and _tag_contains(commit, "rc-v1.0-final")
            )
            rows.append(
                {
                    "run_id": run_id,
                    "run_name": config.get("run_name") or (jobs[0]["run_name"] if jobs else ""),
                    "status": run["status"],
                    "requested_scenario_count": requested,
                    "execution_count": len(executions),
                    "completed_count": completed,
                    "failed_count": failed,
                    "created_at": str(run["created_at"]),
                    "application_commit": commit,
                    "application_version": run["application_version"],
                    "database_records_json": json.dumps(linked_counts, sort_keys=True),
                    "judge_record_count": linked_counts.get("evaluation_ai_judge_scores", 0)
                    + linked_counts.get("ai_judge_results", 0),
                    "artifact_paths_json": json.dumps(artifact_paths),
                    "proposed_action": "KEEP" if is_full_candidate else "DELETE",
                    "reason": (
                        "Checksum-verified frozen d5815fd benchmark imported as one protected logical run: exact active "
                        "125-scenario manifest, 125 terminal/cleanup-complete executions, published 51 deterministic/Judge "
                        "records, registered provenance/report/checksum artifacts, and exact rc-v1.0-final tag target."
                        if is_full_candidate
                        else _delete_reason(len(executions), completed, failed, requested, run["status"], jobs)
                    ),
                }
            )
    kept = [row["run_id"] for row in rows if row["proposed_action"] == "KEEP"]
    if len(kept) != 1:
        raise RuntimeError(f"Expected exactly one protected full-125 run; found {kept}")
    return rows, before_counts, kept[0]


def _delete_reason(
    executions: int, completed: int, failed: int, requested: int, status: str, jobs: list[dict[str, Any]]
) -> str:
    job_statuses = sorted({str(job["status"]) for job in jobs})
    if executions == 0:
        return "Empty/test run with no persisted scenario executions."
    if executions < 125:
        return f"Partial, pilot, focused, duplicate, or temporary run ({completed}/{executions} completed; {failed} failed)."
    if completed != executions or failed:
        return f"Incomplete/failed run ({completed}/{executions} completed; {failed} failed)."
    if status != "completed":
        return f"Run status is {status}, not the uniquely verified completed release run."
    if requested and requested != 125:
        return f"Requested {requested} scenarios rather than the full 125-scenario release manifest."
    if job_statuses:
        return f"Duplicate/non-release run linked to job status(es): {', '.join(job_statuses)}."
    return "Duplicate or non-release run that does not satisfy complete manifest/provenance/artifact checks."


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run inventory for safe evaluation history cleanup")
    parser.add_argument("--output-dir", type=Path, default=Path("research/results/evaluation-cleanup-dry-run"))
    parser.add_argument("--artifact-root", type=Path, default=Path(os.getenv("EVAL_ARTIFACT_ROOT", "research/results")))
    args = parser.parse_args()
    rows, before_counts, retained_run_id = inventory(args.artifact_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "run-inventory.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run",
        "retained_run_id": retained_run_id,
        "run_count": len(rows),
        "keep_count": sum(row["proposed_action"] == "KEEP" for row in rows),
        "delete_count": sum(row["proposed_action"] == "DELETE" for row in rows),
        "before_table_counts": before_counts,
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({**metadata, "inventory": str(csv_path)}, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from evaluation.agentic_benchmark.models import (
    AgenticScenarioCapture,
    AgenticScenarioResult,
    BenchmarkManifestEntry,
    GroundTruthStatus,
    ProtectedGroundTruth,
    ScenarioClassification,
)
from evaluation.agentic_benchmark.scoring import score_scenario
from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.redaction import redact
from evaluation.runners.contracts import ExecutionResult


class BenchmarkSafetyRisk(RuntimeError):
    """Stop the run only when continuing could cause unsafe state changes."""


class AgenticBenchmarkRunner:
    def __init__(
        self,
        *,
        manifest: Iterable[BenchmarkManifestEntry],
        ground_truth: dict[str, ProtectedGroundTruth],
        execute: Callable[[BenchmarkManifestEntry], AgenticScenarioCapture],
        output_root: str | Path,
        database_engine: str = "sqlserver",
        require_full_manifest: bool = True,
    ):
        self.manifest = tuple(manifest)
        self.ground_truth = ground_truth
        self.execute = execute
        self.output_root = Path(output_root)
        self.database_engine = database_engine
        _validate_manifest(
            self.manifest,
            ground_truth,
            require_full_manifest=require_full_manifest,
        )

    def run(self) -> dict[str, Any]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        results: list[AgenticScenarioResult] = []
        for entry in self.manifest:
            try:
                capture = self.execute(entry)
            except BenchmarkSafetyRisk:
                raise
            except Exception as exc:
                capture = AgenticScenarioCapture(
                    scenario_id=entry.scenario_id,
                    database=entry.database,
                    domain=entry.domain,
                    question=entry.question,
                    evidence_status="execution_failed",
                    execution_error=str(exc),
                )
            capture.question = entry.question
            capture.database = entry.database
            capture.domain = entry.domain
            result = score_scenario(
                capture,
                self.ground_truth[entry.scenario_id],
                database_engine=self.database_engine,
            )
            results.append(result)
            self._write_scenario_artifacts(result)
        return self._write_run_outputs(results)

    def _write_scenario_artifacts(self, result: AgenticScenarioResult) -> None:
        folder = self.output_root / "artifacts" / result.capture.scenario_id
        folder.mkdir(parents=True, exist_ok=True)
        safe_capture = redact(asdict(result.capture))
        (folder / "capture.json").write_text(
            json.dumps(safe_capture, indent=2, default=str),
            encoding="utf-8",
        )
        (folder / "score.json").write_text(
            json.dumps(_result_row(result), indent=2, default=str),
            encoding="utf-8",
        )
        (folder / "report.json").write_text(
            json.dumps(redact(result.capture.report_json), indent=2, default=str),
            encoding="utf-8",
        )
        pdf = Path(result.capture.report_pdf)
        if pdf.is_file():
            shutil.copy2(pdf, folder / "investigation-report.pdf")

    def _write_run_outputs(
        self, results: list[AgenticScenarioResult]
    ) -> dict[str, Any]:
        rows = [_result_row(item) for item in results]
        (self.output_root / "scenario-results.json").write_text(
            json.dumps(rows, indent=2, default=str), encoding="utf-8"
        )
        _write_csv(self.output_root / "scenario-results.csv", rows)
        database_summary = _database_summary(results)
        defect_summary = _defect_summary(results)
        metrics = _overall_metrics(results)
        release = _release_recommendation(metrics, defect_summary)
        (self.output_root / "database-summary.json").write_text(
            json.dumps(database_summary, indent=2), encoding="utf-8"
        )
        (self.output_root / "defect-summary.json").write_text(
            json.dumps(defect_summary, indent=2), encoding="utf-8"
        )
        report = _markdown_report(metrics, database_summary, defect_summary, release)
        (self.output_root / "benchmark-report.md").write_text(
            report, encoding="utf-8"
        )
        _write_pdf(
            self.output_root / "benchmark-report.pdf",
            metrics,
            database_summary,
            defect_summary,
            release,
        )
        summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "metrics": metrics,
            "database_summary": database_summary,
            "top_defects": defect_summary[:10],
            "release_recommendation": release,
            "output_root": str(self.output_root.resolve()),
        }
        (self.output_root / "benchmark-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return summary


def capture_from_execution(
    entry: BenchmarkManifestEntry,
    execution: ExecutionResult,
) -> AgenticScenarioCapture:
    detail = execution.raw_response.get("investigation", {})
    extracted = execution.extracted_result
    steps = list(detail.get("agentic_steps") or [])
    step_evidence = [
        item
        for step in steps
        for item in step.get("evidence", [])
        if isinstance(item, dict)
    ]
    persisted_evidence = detail.get("evidence") or extracted.get("evidence") or []
    evidence = step_evidence or [
        item for item in persisted_evidence if isinstance(item, dict)
    ]
    failed = [
        item
        for item in evidence
        if str(item.get("execution_status") or "").lower()
        in {"failed", "timed_out"}
    ]
    blocked = [
        item
        for item in evidence
        if str(item.get("execution_status") or "").lower() == "blocked"
    ]
    absence = [
        item
        for item in evidence
        if str(item.get("evidence_semantics") or "").lower() == "verified_absence"
        and str(item.get("execution_status") or "").lower() == "succeeded"
    ]
    hypotheses = detail.get("root_cause_verifications") or []
    debug_trace = detail.get("debug_trace") or {}
    verified_claims = [
        item for item in hypotheses if item.get("status") == "CONFIRMED"
    ]
    rejected_claims = [
        {"hypothesis_id": item.get("hypothesis_id"), "status": "REJECTED"}
        for item in hypotheses
        if item.get("status") == "REJECTED"
    ]
    rejected_claims.extend(
        item
        for item in debug_trace.get("rejected_or_unsupported_claims", [])
        if isinstance(item, dict)
    )
    budget = steps[-1].get("budget", {}) if steps else {}
    report = detail.get("report_json") or extracted.get("report_snapshot") or {}
    evidence_refs = [
        str(item.get("evidence_id") or "")
        for item in evidence
        if item.get("evidence_id")
    ]
    return AgenticScenarioCapture(
        scenario_id=entry.scenario_id,
        database=entry.database,
        domain=entry.domain,
        question=entry.question,
        investigation_id=execution.investigation_id,
        terminal_state=str(
            detail.get("terminal_state") or execution.investigation_status
        ),
        evidence_status=(
            "verified"
            if any(
                str(item.get("execution_status") or "").lower() == "succeeded"
                for item in evidence
            )
            else "incomplete"
        ),
        steps=steps,
        sql=[str(item) for item in extracted.get("generated_sql", [])],
        sql_count=len(extracted.get("generated_sql", [])),
        verified_absence=absence,
        failed_actions=failed,
        blocked_actions=blocked,
        llm_calls=max(
            int(budget.get("llm_calls") or 0),
            int(bool(debug_trace.get("llm_invoked"))),
        ),
        verified_claims=verified_claims,
        rejected_claims=rejected_claims,
        root_cause_status="CONFIRMED" if verified_claims else "NOT_CONFIRMED",
        fix_readiness=str(detail.get("fix_readiness_state") or "NOT_ASSESSED"),
        identified_entities=_flatten_text(extracted.get("identified_entities", [])),
        discovered_objects=_flatten_text(
            extracted.get("discovered_database_objects", [])
        ),
        findings=_flatten_text(extracted.get("verified_facts", [])),
        recommendations=_flatten_text(extracted.get("recommendations", [])),
        validation_tests=_sections(report, "test", "proof of fix"),
        evidence_records=evidence,
        evidence_facts=_flatten_text(evidence),
        evidence_refs=evidence_refs,
        report_json=report,
        report_pdf=_report_pdf(detail.get("report_artifacts") or {}),
        duration_seconds=float(execution.timings.get("total_seconds") or 0),
        stop_reason=str(detail.get("stop_reason") or ""),
        polling_diagnostics={
            key: value
            for key, value in execution.timings.items()
            if key.startswith("polling_")
        },
        lifecycle_diagnostics=dict(detail.get("lifecycle_diagnostics") or {}),
        execution_error="; ".join(execution.errors)
        if execution.status != "completed"
        else "",
        wrong_investigation_data=(
            bool(detail.get("investigation_id"))
            and str(detail.get("investigation_id")) != execution.investigation_id
        ),
    )


def truth_from_scenario(
    scenario: ScenarioContract,
    review_status: GroundTruthStatus,
) -> ProtectedGroundTruth:
    response_type = scenario.expected_response_type.value
    expected_terminal_states = {
        "confirmed_root_cause": ("ROOT_CAUSE_CONFIRMED",),
        "no_issue_found": ("ISSUE_NOT_REPRODUCED",),
        "insufficient_evidence": ("INSUFFICIENT_EVIDENCE",),
        "multiple_possible_causes": ("INSUFFICIENT_EVIDENCE",),
        "safety_refusal": ("POLICY_BLOCKED",),
    }[response_type]
    return ProtectedGroundTruth(
        scenario_id=scenario.scenario_id,
        review_status=review_status,
        expected_entities=tuple(scenario.expected_entities),
        expected_objects=tuple(
            [
                *scenario.expected_tables,
                *scenario.expected_database_objects,
                *scenario.expected_procedures,
                *scenario.expected_functions,
                *scenario.expected_triggers,
                *scenario.expected_jobs,
            ]
        ),
        expected_evidence=tuple(scenario.required_evidence),
        expected_findings=tuple(scenario.expected_root_cause_concepts),
        expected_recommendations=tuple(scenario.acceptable_fix_concepts),
        expected_terminal_states=expected_terminal_states,
        expected_root_cause_status=(
            "CONFIRMED"
            if response_type == "confirmed_root_cause"
            else ""
        ),
        allowed_domains=(scenario.domain,),
    )


def _validate_manifest(
    manifest: tuple[BenchmarkManifestEntry, ...],
    truth: dict[str, ProtectedGroundTruth],
    *,
    require_full_manifest: bool = True,
) -> None:
    counts = Counter(item.domain for item in manifest)
    if require_full_manifest:
        if len(manifest) != 25 or any(counts[domain] != 5 for domain in counts):
            raise ValueError(
                "AG-10 manifest must contain exactly five scenarios per database"
            )
        if len(counts) != 5:
            raise ValueError("AG-10 manifest must cover exactly five databases")
    elif not manifest:
        raise ValueError("Controlled AG-10 validation must select at least one scenario")
    ids = [item.scenario_id for item in manifest]
    if len(set(ids)) != len(ids):
        raise ValueError("AG-10 scenario IDs must be unique")
    if set(ids) != set(truth):
        raise ValueError("Protected ground truth must match the manifest exactly")


def _result_row(result: AgenticScenarioResult) -> dict[str, Any]:
    capture = result.capture
    return {
        "scenario_id": capture.scenario_id,
        "database": capture.database,
        "domain": capture.domain,
        "question": capture.question,
        "investigation_id": capture.investigation_id,
        "terminal_state": capture.terminal_state,
        "evidence_status": capture.evidence_status,
        "step_count": len(capture.steps),
        "sql_count": capture.sql_count,
        "verified_absence_count": len(capture.verified_absence),
        "failed_action_count": len(capture.failed_actions),
        "blocked_action_count": len(capture.blocked_actions),
        "llm_calls": capture.llm_calls,
        "verified_claim_count": len(capture.verified_claims),
        "rejected_claim_count": len(capture.rejected_claims),
        "root_cause_status": capture.root_cause_status,
        "fix_readiness": capture.fix_readiness,
        "report_json_available": bool(capture.report_json),
        "report_pdf_available": bool(capture.report_pdf),
        "duration_seconds": capture.duration_seconds,
        "stop_reason": capture.stop_reason,
        "ground_truth_status": result.ground_truth_status.value,
        "classification": result.classification.value,
        **asdict(result.scores),
        "score": result.scores.total,
        "automatic_failures": ";".join(result.automatic_failures),
        "defects": ";".join(result.defects),
        "execution_error": capture.execution_error,
    }


def _database_summary(results: list[AgenticScenarioResult]) -> list[dict[str, Any]]:
    grouped: dict[str, list[AgenticScenarioResult]] = defaultdict(list)
    for item in results:
        grouped[item.capture.database].append(item)
    rows = []
    for database, items in sorted(grouped.items()):
        formal = [
            item
            for item in items
            if item.ground_truth_status is GroundTruthStatus.REVIEWED
        ]
        rows.append(
            {
                "database": database,
                "scenario_count": len(items),
                "reviewed_count": len(formal),
                "exact_pass_count": sum(
                    item.classification is ScenarioClassification.PASS
                    for item in formal
                ),
                "exact_pass_accuracy": round(
                    sum(
                        item.classification is ScenarioClassification.PASS
                        for item in formal
                    )
                    / len(formal),
                    4,
                )
                if formal
                else None,
                "average_score": round(
                    mean(item.scores.total for item in formal), 3
                )
                if formal
                else None,
                "automatic_failure_count": sum(
                    bool(item.automatic_failures) for item in items
                ),
            }
        )
    return rows


def _overall_metrics(results: list[AgenticScenarioResult]) -> dict[str, Any]:
    formal = [
        item
        for item in results
        if item.ground_truth_status is GroundTruthStatus.REVIEWED
    ]
    passes = sum(
        item.classification is ScenarioClassification.PASS for item in formal
    )
    return {
        "scenario_count": len(results),
        "completed_investigation_count": sum(
            bool(item.capture.investigation_id) for item in results
        ),
        "reviewed_ground_truth_count": len(formal),
        "needs_ground_truth_review_count": len(results) - len(formal),
        "formal_exact_pass_count": passes,
        "formal_exact_pass_accuracy": round(passes / len(formal), 4)
        if formal
        else None,
        "average_score": round(mean(item.scores.total for item in formal), 3)
        if formal
        else None,
        "automatic_failure_count": sum(
            bool(item.automatic_failures) for item in results
        ),
        "execution_failure_count": sum(
            item.classification is ScenarioClassification.EXECUTION_FAILED
            for item in results
        ),
    }


def _defect_summary(results: list[AgenticScenarioResult]) -> list[dict[str, Any]]:
    defects = Counter(defect for item in results for defect in item.defects)
    return [
        {"defect": name, "scenario_count": count}
        for name, count in defects.most_common()
    ]


def _release_recommendation(
    metrics: dict[str, Any], defects: list[dict[str, Any]]
) -> dict[str, str]:
    accuracy = metrics["formal_exact_pass_accuracy"]
    ready = (
        metrics["scenario_count"] == 25
        and metrics["completed_investigation_count"] == 25
        and metrics["automatic_failure_count"] == 0
        and metrics["execution_failure_count"] == 0
        and accuracy is not None
        and accuracy >= 0.8
    )
    return {
        "decision": "RELEASE_CANDIDATE" if ready else "DO_NOT_RELEASE",
        "reason": (
            "All safety gates passed and formal exact-pass accuracy met 80%."
            if ready
            else "Release gate not met; resolve execution, safety, or accuracy defects."
        ),
        "top_defect": defects[0]["defect"] if defects else "none",
    }


def _markdown_report(metrics, databases, defects, release) -> str:
    lines = [
        "# AG-10 Agentic Benchmark Report",
        "",
        f"- Release recommendation: **{release['decision']}**",
        f"- Formal exact-pass accuracy: {metrics['formal_exact_pass_accuracy']}",
        f"- Reviewed scenarios: {metrics['reviewed_ground_truth_count']}",
        f"- Needs ground-truth review: {metrics['needs_ground_truth_review_count']}",
        f"- Automatic failures: {metrics['automatic_failure_count']}",
        "",
        "## Database summary",
        "",
        "| Database | Scenarios | Reviewed | Exact passes | Accuracy | Average score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['database']} | {row['scenario_count']} | {row['reviewed_count']} | "
        f"{row['exact_pass_count']} | {row['exact_pass_accuracy']} | "
        f"{row['average_score']} |"
        for row in databases
    )
    lines.extend(["", "## Top defects", ""])
    lines.extend(
        f"- {row['defect']}: {row['scenario_count']} scenarios"
        for row in defects[:10]
    )
    lines.extend(["", "## Release rationale", "", release["reason"], ""])
    return "\n".join(lines)


def _write_pdf(path, metrics, databases, defects, release) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph("AG-10 Agentic Benchmark Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            f"Release recommendation: {release['decision']}", styles["Heading2"]
        ),
        Paragraph(release["reason"], styles["BodyText"]),
        Spacer(1, 12),
    ]
    metric_rows = [["Metric", "Value"]] + [
        [key.replace("_", " ").title(), str(value)]
        for key, value in metrics.items()
    ]
    table = Table(metric_rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )
    story.extend([table, Spacer(1, 12), Paragraph("Database summary", styles["Heading2"])])
    database_rows = [
        ["Database", "Scenarios", "Reviewed", "Passes", "Accuracy", "Score"]
    ] + [
        [
            row["database"],
            row["scenario_count"],
            row["reviewed_count"],
            row["exact_pass_count"],
            row["exact_pass_accuracy"],
            row["average_score"],
        ]
        for row in databases
    ]
    story.append(Table(database_rows))
    story.extend([Spacer(1, 12), Paragraph("Top defects", styles["Heading2"])])
    for row in defects[:10]:
        story.append(
            Paragraph(
                f"{row['defect']}: {row['scenario_count']} scenarios",
                styles["BodyText"],
            )
        )
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _flatten_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, sort_keys=True, default=str)]
    if isinstance(value, list):
        return [
            item if isinstance(item, str) else json.dumps(item, sort_keys=True, default=str)
            for item in value
        ]
    return []


def _sections(report: dict[str, Any], *terms: str) -> list[str]:
    return [
        json.dumps(item, sort_keys=True, default=str)
        for item in report.get("sections", [])
        if any(term in str(item.get("title") or "").lower() for term in terms)
    ]


def _report_pdf(artifacts: dict[str, Any]) -> str:
    for key, value in artifacts.items():
        if str(key).lower().endswith(".pdf") or str(value).lower().endswith(".pdf"):
            return str(value)
    return ""

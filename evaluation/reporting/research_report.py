from __future__ import annotations

import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from evaluation.framework.models import (
    EvaluationAIJudgeScoreModel as Judge,
    EvaluationDeterministicScoreModel as Deterministic,
    EvaluationHumanReviewFlagModel as Review,
    EvaluationRunModel as Run,
    EvaluationScenarioExecutionModel as Execution,
    TestScenarioModel as Scenario,
)
from legacydb_copilot.db.session import create_session_factory


def _json(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _latest(rows, key):
    result = {}
    for row in rows:
        marker = key(row)
        if marker not in result or row.created_at > result[marker].created_at:
            result[marker] = row
    return result


def _bar_chart(path: Path, title: str, values: dict[str, float], suffix: str = "") -> None:
    image = Image.new("RGB", (1000, 520), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    draw.text((35, 25), title, fill="#172554", font=font)
    if not values:
        draw.text((35, 90), "No data", fill="#64748b", font=font)
    else:
        maximum = max(max(values.values()), 1)
        for index, (label, value) in enumerate(values.items()):
            y = 90 + index * min(70, 350 // max(len(values), 1))
            width = int(700 * value / maximum)
            draw.text((35, y), str(label)[:24], fill="#334155", font=font)
            draw.rectangle((245, y, 245 + width, y + 25), fill="#2563eb")
            draw.text((260 + width, y), f"{value:.2f}{suffix}", fill="#0f172a", font=font)
    image.save(path)


def generate_research_report(run_id: str, output_root: Path | None = None) -> dict:
    url = os.getenv("EVAL_RESULTS_DATABASE_URL")
    if not url:
        raise RuntimeError("EVAL_RESULTS_DATABASE_URL is not configured")
    factory = create_session_factory(url)
    with factory() as db:
        run = db.get(Run, run_id)
        if not run:
            raise ValueError(f"Evaluation run not found: {run_id}")
        executions = list(db.scalars(select(Execution).where(Execution.evaluation_run_id == run_id)))
        scenario_ids = [row.test_scenario_id for row in executions]
        scenarios = {row.id: row for row in db.scalars(select(Scenario).where(Scenario.id.in_(scenario_ids)))} if scenario_ids else {}
        execution_ids = [row.id for row in executions]
        det_rows = list(db.scalars(select(Deterministic).where(Deterministic.scenario_execution_id.in_(execution_ids)))) if execution_ids else []
        judge_rows = list(db.scalars(select(Judge).where(Judge.scenario_execution_id.in_(execution_ids)))) if execution_ids else []
        det = _latest(det_rows, lambda row: row.scenario_execution_id)
        judges = _latest(judge_rows, lambda row: row.scenario_execution_id)
        det_ids = [row.id for row in det.values()]
        reviews = {row.deterministic_score_id: row for row in db.scalars(select(Review).where(Review.deterministic_score_id.in_(det_ids)))} if det_ids else {}

    records = []
    for execution in executions:
        scenario = scenarios.get(execution.test_scenario_id)
        score = det.get(execution.id)
        judge = judges.get(execution.id)
        normalized = _json(judge.normalized_result_json, {}) if judge else {}
        result = _json(execution.result_json, {})
        score_details = _json(score.details_json, {}) if score else {}
        expectations = _json(scenario.expectations_json, {}) if scenario else {}
        timing = _json(execution.timing_json, {})
        errors = _json(execution.errors_json, [])
        review = reviews.get(score.id) if score else None
        records.append({
            "scenario_id": execution.scenario_id, "domain": execution.domain,
            "difficulty": scenario.difficulty if scenario else "unknown",
            "category": scenario.category if scenario else "unknown",
            "database_engine": expectations.get("database_engine", "unknown"),
            "question": scenario.question if scenario else "",
            "expected_answer": json.dumps(_json(scenario.expectations_json, {}), ensure_ascii=False) if scenario else "",
            "application_answer": result.get("answer") or result.get("application_answer") or "",
            "status": execution.status, "investigation_status": execution.investigation_status,
            "investigation_id": execution.investigation_id,
            "canonical_investigated_entity": result.get("canonical_investigated_entity") or score_details.get("canonical_investigated_entity") or "",
            "evidence_linked_entities": json.dumps(result.get("evidence_linked_entities") or score_details.get("evidence_linked_entities") or [], ensure_ascii=False),
            "entity_provenance": json.dumps(result.get("entity_provenance") or {}, ensure_ascii=False),
            "benchmark_validity": score_details.get("benchmark_validity", "valid"),
            "deterministic_pass": bool(score and not score.critical_failure and float(score.final_score) >= 70),
            "deterministic_score": float(score.final_score) if score else None,
            "unadjusted_score": float(score.unadjusted_score) if score else None,
            "classification": score.classification if score else "not_scored",
            "ai_judge_score": float(judge.weighted_score) if judge else None,
            "judge_explanation": normalized.get("explanation") or normalized.get("rationale") or "",
            "confidence": normalized.get("confidence"),
            "latency_seconds": timing.get("total_seconds"),
            "input_tokens": judge.input_tokens if judge else 0, "output_tokens": judge.output_tokens if judge else 0,
            "estimated_cost_usd": float(judge.estimated_cost_usd) if judge else 0,
            "model_version": judge.model if judge else "", "prompt_version": judge.prompt_version if judge else "",
            "human_review_required": bool(review and review.required),
            "human_review_reasons": json.dumps(_json(review.reasons_json, []), ensure_ascii=False) if review else "[]",
            "failure": "; ".join(map(str, errors)) if errors else (score.classification if score and score.critical_failure else ""),
            "persisted_result_row": True,
        })

    output = (output_root or Path(os.getenv("EVAL_ARTIFACT_ROOT", "research/results"))) / run_id
    charts = output / "charts"; charts.mkdir(parents=True, exist_ok=True)
    numeric = lambda key: [float(row[key]) for row in records if row.get(key) is not None]
    completed = sum(row["status"] == "completed" for row in records)
    det_pass = sum(row["deterministic_pass"] for row in records)
    by_domain = defaultdict(list); by_difficulty = defaultdict(list)
    for row in records:
        if row["ai_judge_score"] is not None:
            by_domain[row["domain"]].append(row["ai_judge_score"])
            by_difficulty[row["difficulty"]].append(row["ai_judge_score"])
    domain_scores = {key: mean(value) for key, value in sorted(by_domain.items())}
    difficulty_scores = {key: mean(value) for key, value in sorted(by_difficulty.items())}
    failures = Counter(row["failure"] or "none" for row in records)
    _bar_chart(charts / "score-by-domain.png", "AI Judge score by domain", domain_scores)
    _bar_chart(charts / "score-by-difficulty.png", "AI Judge score by difficulty", difficulty_scores)
    _bar_chart(charts / "pass-fail.png", "Deterministic pass/fail", {"Pass": det_pass, "Fail": len(records)-det_pass})
    _bar_chart(charts / "latency.png", "Latency by scenario (seconds)", {row["scenario_id"]: float(row["latency_seconds"] or 0) for row in records}, "s")
    _bar_chart(charts / "failure-categories.png", "Failure categories", dict(failures))
    _bar_chart(charts / "cost-by-domain.png", "Estimated Judge cost by domain (USD)", {domain: sum(row["estimated_cost_usd"] for row in records if row["domain"] == domain) for domain in sorted({row["domain"] for row in records})})

    summary = {
        "run_id": run_id, "application_commit": run.application_commit, "application_version": run.application_version,
        "run_status": run.status, "scenario_count": len(records), "completed": completed,
        "operational_completion_rate": completed / len(records) if records else 0,
        "overall_accuracy": det_pass / len(records) if records else 0,
        "deterministic_pass_rate": det_pass / len(records) if records else 0,
        "ai_judge_average_score": mean(numeric("ai_judge_score")) if numeric("ai_judge_score") else None,
        "latency_mean_seconds": mean(numeric("latency_seconds")) if numeric("latency_seconds") else None,
        "latency_median_seconds": median(numeric("latency_seconds")) if numeric("latency_seconds") else None,
        "total_tokens": sum(row["input_tokens"] + row["output_tokens"] for row in records),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in records),
        "human_review_required": sum(row["human_review_required"] for row in records),
        "domain_scores": domain_scores, "difficulty_scores": difficulty_scores,
        "configuration": _json(run.configuration_json, {}), "timing_cost": _json(run.timing_cost_json, {}),
    }
    (output / "results.json").write_text(json.dumps({"summary": summary, "scenarios": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = list(records[0]) if records else ["scenario_id"]
    with (output / "scenario-results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(records)
    sections = [
        ("Executive summary", f"This local-first run evaluated {len(records)} scenario(s); {completed} completed operationally. Deterministic pass rate: {summary['deterministic_pass_rate']:.1%}. AI Judge mean: {summary['ai_judge_average_score'] if summary['ai_judge_average_score'] is not None else 'N/A'}."),
        ("Methodology", f"Versioned scenarios were reset and injected into isolated local {', '.join(sorted({row['database_engine'] for row in records})) or 'configured'} databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge."),
        ("Databases and domains tested", ", ".join(sorted({row['domain'] for row in records})) or "None"),
        ("Scenario distribution", f"Domains: {dict(Counter(row['domain'] for row in records))}. Difficulties: {dict(Counter(row['difficulty'] for row in records))}."),
        ("Accuracy and quality", f"Operational completion: {summary['operational_completion_rate']:.1%}. Overall accuracy: {summary['overall_accuracy']:.1%}. Deterministic pass rate: {summary['deterministic_pass_rate']:.1%}. Domain scores: {domain_scores}. Difficulty scores: {difficulty_scores}."),
        ("Latency, tokens, and cost", f"Mean latency: {summary['latency_mean_seconds']} s; median: {summary['latency_median_seconds']} s; tokens: {summary['total_tokens']}; estimated Judge cost: ${summary['estimated_cost_usd']:.6f}."),
        ("Failure categories", json.dumps(dict(failures), ensure_ascii=False)),
        ("False-positive and false-negative analysis", "Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence."),
        ("Human review required", f"{summary['human_review_required']} case(s) flagged. See scenario-level CSV."),
        ("Limitations", "This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent."),
        ("Reproducibility", f"Run ID: {run_id}; application version: {run.application_version}; commit: {run.application_commit}. Full configuration is stored in results.json with secrets excluded."),
    ]
    md = "# LegacyDB Copilot AI Judge Evaluation Report\n\n" + "\n\n".join(f"## {title}\n\n{text}" for title, text in sections)
    (output / "research-report.md").write_text(md, encoding="utf-8")
    cards = "".join(f"<div class='card'><h3>{html.escape(title)}</h3><p>{html.escape(str(text))}</p></div>" for title, text in sections)
    images = "".join(f"<figure><img src='charts/{name}'><figcaption>{name}</figcaption></figure>" for name in ("score-by-domain.png", "score-by-difficulty.png", "pass-fail.png", "latency.png", "failure-categories.png", "cost-by-domain.png"))
    table_rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(row.get(key, '')))}</td>" for key in ("scenario_id", "domain", "difficulty", "status", "benchmark_validity", "canonical_investigated_entity", "deterministic_score", "ai_judge_score", "investigation_id")) + "</tr>" for row in records)
    document = f"<!doctype html><html><head><meta charset='utf-8'><title>Evaluation report</title><style>body{{font:16px system-ui;margin:40px;color:#172554}}.card{{border-left:5px solid #2563eb;padding:8px 18px;margin:16px 0;background:#f8fafc}}img{{max-width:760px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #cbd5e1;text-align:left}}</style></head><body><h1>LegacyDB Copilot AI Judge Evaluation Report</h1>{cards}<h2>Charts</h2>{images}<h2>Scenario-level results</h2><table><tr><th>Scenario</th><th>Domain</th><th>Difficulty</th><th>Status</th><th>Validity</th><th>Canonical entity</th><th>Deterministic</th><th>Judge</th><th>Investigation</th></tr>{table_rows}</table></body></html>"
    (output / "research-report.html").write_text(document, encoding="utf-8")
    return {"run_id": run_id, "output_directory": str(output.resolve()), "summary": summary, "artifacts": sorted(str(path.resolve()) for path in output.rglob("*") if path.is_file())}

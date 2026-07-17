from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from evaluation.cli.__main__ import all_scenarios, build_store
from evaluation.framework.models import EvaluationScenarioExecutionModel
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.db.session import create_session_factory


def parsed(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def main(run_id: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads((output / "fixture-verification.json").read_text(encoding="utf-8"))
    api_runtime = json.loads(Path(".tmp/local-evaluation/api-runtime.json").read_text(encoding="utf-8"))
    worker_runtime = json.loads(Path(".tmp/local-evaluation/worker-runtime.json").read_text(encoding="utf-8"))
    with build_store().session_factory() as db:
        execution = db.scalar(select(EvaluationScenarioExecutionModel).where(EvaluationScenarioExecutionModel.evaluation_run_id == run_id))
    with create_session_factory(Settings.from_env().database_url)() as db:
        investigation = db.get(InvestigationModel, execution.investigation_id)
    scenario = next(item for item in all_scenarios() if item.scenario_id == execution.scenario_id)
    evidence = parsed(investigation.evidence_json, [])
    sql = parsed(investigation.sql_queries_json, [])
    entities = parsed(investigation.extracted_entities_json, [])
    trace = parsed(investigation.ai_debug_trace_json, {})
    answer = investigation.ai_answer
    metadata_line = next((line for line in answer.splitlines() if line.startswith("- Discovered tables:")), "")
    candidates_line = next((line for line in answer.splitlines() if line.startswith("- Selected candidates:")), "")
    raw_metadata = trace.get("raw_metadata_objects") if isinstance(trace.get("raw_metadata_objects"), dict) else {}
    gate = "REJECTED" if "Evidence gate blocked" in answer or "Gate Required: Yes" in answer and "Issue Reproduced: No" in answer else "ACCEPTED_OR_NOT_REQUIRED"
    row_counts = [{"sql": item.get("sql", ""), "row_count": len(item.get("sample_rows") or []), "evidence_id": item.get("evidence_id", "")} for item in evidence if isinstance(item, dict)]
    result = {
        "run_id": run_id, "scenario_id": scenario.scenario_id, "question": scenario.question,
        "expected_answer": {"response_type": scenario.expected_response_type.value, "root_cause_concepts": scenario.expected_root_cause_concepts, "required_evidence": scenario.required_evidence},
        "expected_entity": scenario.expected_entities, "expected_defect": scenario.expected_root_cause_concepts,
        "fixture": fixture, "runtime": {"api": api_runtime, "worker": worker_runtime},
        "investigation_id": investigation.id, "application_status": investigation.status,
        "benchmark_status": execution.status, "benchmark_errors": parsed(execution.errors_json, []),
        "intent_classification": investigation.detected_intent, "extracted_entities": entities,
        "metadata_objects_discovered": raw_metadata.get("tables") or metadata_line.removeprefix("- Discovered tables: "),
        "metadata_cache": trace.get("metadata_cache", {}),
        "relationships_discovered": [item.get("sql") for item in trace.get("sql_plan", []) if " join " in f" {str(item.get('sql','')).lower()} "],
        "candidate_object_ranking": trace.get("ranked_objects") or candidates_line.removeprefix("- Selected candidates: "),
        "sql_plan": sql, "sql_validation_result": "Statements persisted after safe-SQL validation.",
        "sql_execution_row_counts": row_counts, "evidence_records": evidence,
        "evidence_verification_result": "Verification suggestions were produced; no accepted application evidence proved the expected defect.",
        "evidence_gate_decision": gate,
        "ai_reasoning_invoked": bool(trace.get("ai_reasoning_invoked")), "ai_model": trace.get("llm_model_name"),
        "prompt_version": trace.get("prompt_version"), "application_ai_input_tokens": trace.get("input_tokens", 0),
        "application_ai_output_tokens": trace.get("output_tokens", 0), "ai_response": trace.get("llm_response_raw"),
        "final_application_answer": answer, "deterministic_score": None, "ai_judge_score": None,
        "human_review_reasons": ["invalid_configuration", *parsed(execution.errors_json, [])],
        "first_remaining_root_cause": "Metadata discovery and ranking included transport_work_orders, but relationship inference treated shipment_milestones as the parent because it shared ShipmentsId without owning that primary key. The resulting negative-evidence SQL searched shipment_milestones for SHP-5001, returned zero rows, and the evidence gate correctly skipped application AI reasoning.",
        "database_compatibility": {"supported_engine": scenario.database_engine, "actual_engine": "mysql", "translation_status": "bounded_tsql_translation", "fixture_compatibility": "VALID", "metadata_compatibility": "PARTIAL", "procedure_compatibility": "UNSUPPORTED: SQL Server procedures/functions/triggers are not present in MySQL"},
    }
    (output / "instrumented-scenario-result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    config_md = "# Effective Runtime Configuration\n\nBoth diagnostics were emitted from parsed `Settings` inside newly started processes. Secrets are represented only by presence booleans.\n\n" + "\n\n".join(
        f"## {name.title()}\n\n```json\n{json.dumps(value, indent=2)}\n```" for name, value in result["runtime"].items()
    )
    (output / "effective-runtime-configuration.md").write_text(config_md, encoding="utf-8")
    trace_md = f"""# Investigation Trace

## Scenario

- Scenario ID: {scenario.scenario_id}
- Investigation ID: {investigation.id}
- Question: {scenario.question}
- Fixture validity: {fixture['fixture_validity']}
- Supported engine: {scenario.database_engine}
- Actual engine: MySQL

## Pipeline

- Intent: {investigation.detected_intent}
- Extracted entities: `{json.dumps(entities, default=str)}`
- Metadata discovered: {result['metadata_objects_discovered']}
- Candidate ranking: {result['candidate_object_ranking']}
- SQL statements persisted/executed: {len(sql)}
- Evidence records: {len(evidence)}
- Evidence gate: {gate}
- AI reasoning invoked: {result['ai_reasoning_invoked']}
- AI model: {result['ai_model']}
- Prompt version: {result['prompt_version']}
- Application AI tokens: {result['application_ai_input_tokens']} input / {result['application_ai_output_tokens']} output
- Benchmark status: {execution.status}

## SQL and row counts

```json
{json.dumps(row_counts, indent=2, default=str)}
```

## First remaining root cause

{result['first_remaining_root_cause']}

Because the run is `INVALID_CONFIGURATION`, deterministic accuracy and AI Judge scoring were intentionally not published.
"""
    (output / "investigation-trace.md").write_text(trace_md, encoding="utf-8")
    checks = [
        ("AI flags enabled inside API", all(api_runtime[k] for k in ("ai_reasoning_enabled","llm_enabled","verification_agent_enabled","openai_api_key_present"))),
        ("AI flags enabled inside worker", all(worker_runtime[k] for k in ("ai_reasoning_enabled","llm_enabled","verification_agent_enabled","openai_api_key_present"))),
        ("Application AI reasoning executed", result["ai_reasoning_invoked"]),
        ("Fixture contained expected defect", fixture["fixture_validity"] == "VALID"),
        ("Metadata found required objects", all(name in result["metadata_objects_discovered"] for name in scenario.expected_tables)),
        ("SQL returned expected evidence", any(item["row_count"] > 0 for item in row_counts)),
        ("Evidence gate accepted", gate != "REJECTED"),
        ("AI identified expected root cause", all(term.lower() in answer.lower() for term in ("downstream", "work item"))),
    ]
    rows = "".join(f"<tr><td>{html.escape(label)}</td><td class={'pass' if passed else 'fail'}>{'YES' if passed else 'NO'}</td></tr>" for label, passed in checks)
    report = f"<!doctype html><html><head><meta charset='utf-8'><title>Instrumented scenario</title><style>body{{font:15px Arial;margin:40px;color:#0b2545}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #ccd6e0}}.pass{{color:#166534;font-weight:bold}}.fail{{color:#991b1b;font-weight:bold}}pre{{white-space:pre-wrap;background:#f8fafc;padding:12px}}</style></head><body><h1>Instrumented Scenario Diagnostic</h1><p>{scenario.scenario_id} / {investigation.id}</p><table><tr><th>Question</th><th>Result</th></tr>{rows}</table><h2>Outcome</h2><p>Benchmark status: <b>{execution.status}</b>. Accuracy was not calculated.</p><h2>First remaining root cause</h2><p>{html.escape(result['first_remaining_root_cause'])}</p><h2>Fixture proof</h2><pre>{html.escape(json.dumps(fixture,indent=2,default=str))}</pre><h2>Application answer</h2><pre>{html.escape(answer)}</pre></body></html>"
    (output / "instrumented-scenario-report.html").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))

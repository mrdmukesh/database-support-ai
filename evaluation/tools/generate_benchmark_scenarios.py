from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOMAINS = {
    "banking": {"prefix": "BNK", "objects": ["transactions", "transfers", "payment_instructions", "accounts", "beneficiaries", "loans", "cards", "fraud_alerts"], "subject": "payment", "trigger": "eval.tr_accounts_audit"},
    "orders": {"prefix": "ORD", "objects": ["sales_orders", "sales_order_lines", "allocations", "pick_tasks", "shipments", "inventory_movements", "receipts", "purchase_orders"], "subject": "order", "trigger": "eval.tr_products_audit"},
    "shipping": {"prefix": "SHP", "objects": ["shipments", "bookings", "container_assignments", "container_events", "shipment_milestones", "transport_work_orders", "voyages", "bills_of_lading"], "subject": "shipment", "trigger": "eval.tr_bookings_audit"},
    "payroll": {"prefix": "PAY", "objects": ["payroll_runs", "payroll_items", "payments", "time_entries", "deductions", "employees", "tax_filings", "leave_requests"], "subject": "payroll item", "trigger": "eval.tr_employees_audit"},
    "clinic": {"prefix": "CLN", "objects": ["appointments", "encounters", "claims", "lab_orders", "lab_results", "prescriptions", "payments", "procedures_performed"], "subject": "patient service", "trigger": "eval.tr_providers_audit"},
}

CATEGORIES = [
    ("exact_entity_lookup", "easy", "Investigate why {subject} {entity} is marked Failed even though its request was accepted.", "the exact business key resolves to one failed record", "restore the record through the owning workflow after validating the request"),
    ("partial_entity_resolution", "easy", "Investigate the failed {subject} reported as {partial}; resolve the complete identifier before diagnosing it.", "a safe candidate lookup resolves the partial identifier to one record", "confirm the resolved identifier and retry through the supported workflow"),
    ("ambiguous_entity_resolution", "hard", "Investigate {subject} {partial}; support reported a failure but did not provide the final suffix.", "the partial identifier matches multiple plausible records and investigation must stop", "request user selection of the correct candidate before continuing"),
    ("missing_downstream_record", "medium", "Investigate why completed {subject} {entity} has no downstream processing record.", "the upstream record completed but its correlated integration record is missing", "reconcile the missing downstream work through an idempotent workflow"),
    ("duplicate_transaction", "medium", "Investigate why {subject} {entity} produced two processing messages for one business request.", "two correlated processing events represent one business action", "deduplicate using a stable business idempotency key"),
    ("workflow_interruption", "medium", "Investigate why {subject} {entity} stopped between validation and completion.", "workflow history ends at an intermediate state with an exception", "resume from the last committed workflow checkpoint"),
    ("exception_handling", "medium", "Investigate why exception handling left {subject} {entity} in Processing.", "the exception was recorded but no compensating transition ran", "add observable compensation and terminal-state handling"),
    ("integration_failure", "medium", "Investigate why external integration for {subject} {entity} was rejected.", "the correlated integration message failed and blocked completion", "correct the integration contract and safely replay the message"),
    ("queue_backlog", "medium", "Investigate why {subject} {entity} remains Queued behind older work.", "queue evidence shows the entity has not been consumed", "drain the queue with bounded, monitored processing"),
    ("retry_failure", "hard", "Investigate why all retries for {subject} {entity} failed without a terminal status.", "retry evidence records exhausted attempts and the entity remained pending", "route exhausted retries to reviewed dead-letter recovery"),
    ("audit_history_inconsistency", "hard", "Investigate why audit history says {subject} {entity} completed while its business record says Failed.", "business and audit states conflict for the same correlation", "reconcile history from the authoritative transaction boundary"),
    ("missing_reference_data", "easy", "Investigate why {subject} {entity} failed validation after a reference lookup.", "required active reference data is absent from discovered relationships", "restore governed reference data before replaying the workflow"),
    ("stored_procedure_defect", "hard", "Investigate why workflow procedure processing left {subject} {entity} in the wrong status.", "procedure definition targets the workflow object but the observed transition is incorrect", "version and test the procedure correction before controlled replay"),
    ("trigger_failure", "hard", "Investigate why updating {subject} {entity} produced no consistent audit outcome.", "trigger metadata is relevant but the expected correlated audit transition is absent", "repair trigger behavior and reconcile missing audit events"),
    ("batch_processing_failure", "medium", "Investigate why batch processing failed for {subject} {entity} while neighboring items completed.", "the correlated batch or integration evidence isolates one failed item", "restart only the failed item with checkpoint protection"),
    ("concurrency_race_condition", "expert", "Investigate intermittent competing updates for {subject} {entity} that produced inconsistent terminal states.", "same-correlation events at overlapping timestamps show a lost-update race", "use optimistic concurrency and retry on version conflict"),
    ("transaction_rollback", "hard", "Investigate why {subject} {entity} reports completion although downstream changes were rolled back.", "exception and audit evidence show the unit of work rolled back", "make the status transition atomic with downstream writes"),
    ("idempotency_issue", "expert", "Investigate why replaying {subject} {entity} repeated a previously accepted operation.", "replay created a second correlated operation without an idempotency guard", "enforce a unique idempotency key across retries"),
    ("incorrect_business_status", "easy", "Investigate why {subject} {entity} displays Completed while failure evidence remains open.", "the business status contradicts active correlated failure evidence", "derive status from authoritative workflow completion"),
    ("multi_table_investigation", "medium", "Investigate the end-to-end failure of {subject} {entity} across business, integration, exception, and audit records.", "correlated multi-table evidence traces the failure to one interrupted transition", "repair the transition and reconcile each correlated downstream state"),
]

SCORES = {"root_cause": 90, "evidence": 90, "object_discovery": 85, "recommendation": 85, "citation": 90, "sql_safety": 100, "completeness": 90}


def generate(domain: str) -> None:
    cfg = DOMAINS[domain]
    domain_root = ROOT / "evaluation_scenarios" / domain
    manifest_path = domain_root / "scenarios.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = [item for item in existing if "-benchmark-" not in item["scenario_id"]]
    created = []
    for index, (category, difficulty, question, cause, remediation) in enumerate(CATEGORIES, 1):
        scenario_id = f"{domain}-benchmark-{index:03d}"
        entity = f"{cfg['prefix']}-2026-{index:04d}-A"
        partial = entity.rsplit("-", 1)[0]
        target = cfg["objects"][(index - 1) % len(cfg["objects"])]
        correlation = f"EVAL-{domain.upper()}-{100 + index:03d}"
        procedure = f"eval.usp_{domain}_workflow_{((index - 1) % 8) + 1}"
        scenario_dir = domain_root / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        scripts = _scripts(domain, category, target, entity, partial, correlation)
        for filename, content in scripts.items():
            (scenario_dir / filename).write_text(content, encoding="utf-8", newline="\n")
        expected_response = "multiple_possible_causes" if category == "ambiguous_entity_resolution" else "confirmed_root_cause"
        human_review = category == "ambiguous_entity_resolution"
        item = {
            "scenario_id": scenario_id, "scenario_version": 1, "active": True,
            "domain": domain, "database_engine": "sqlserver", "database_version": "Azure SQL Database / SQL Server 2022",
            "category": category, "subcategory": category, "difficulty": difficulty,
            "business_description": f"A synthetic {domain} production-support incident testing {category.replace('_', ' ')} without exposing ground truth to runtime code.",
            "question": question.format(subject=cfg["subject"], entity=entity, partial=partial),
            "baseline_script": f"evaluation_scenarios/{domain}/{scenario_id}/baseline_reset.sql",
            "setup_script": f"evaluation_scenarios/{domain}/{scenario_id}/inject.sql",
            "verification_script": f"evaluation_scenarios/{domain}/{scenario_id}/verify.sql",
            "cleanup_script": f"evaluation_scenarios/{domain}/{scenario_id}/cleanup.sql",
            "expected_response_type": expected_response,
            "expected_entities": [partial] if human_review else [entity],
            "expected_entity_value": entity,
            "expected_entity_question_value": partial if category in {"partial_entity_resolution", "ambiguous_entity_resolution"} else entity,
            "expected_entity_type": category,
            "expected_entity_schema": "eval",
            "expected_entity_table": target,
            "expected_entity_column": "BusinessKey",
            "expected_entity_match_mode": "partial_ambiguous" if human_review else "exact",
            "expected_entity_database": f"Eval{domain.title()}",
            "expected_defect_table": "exceptions",
            "expected_defect_column": "CorrelationId",
            "expected_defect_value": correlation,
            "expected_entity_link_column": "CorrelationId",
            "expected_defect_link_column": "CorrelationId",
            "expected_root_cause_concepts": [cause],
            "expected_tables": [target, "integration_messages", "exceptions", "audit_history"],
            "expected_columns": ["BusinessKey", "Status", "EventTime", "CorrelationId", "Details"],
            "expected_database_objects": [f"eval.{target}", "eval.integration_messages", "eval.exceptions", "eval.audit_history"],
            "expected_procedures": [procedure], "expected_functions": [f"eval.fn_{domain}_active_status"],
            "expected_triggers": [cfg["trigger"]], "expected_jobs": [],
            "expected_relationships": [f"eval.{target}.CorrelationId -> eval.integration_messages.CorrelationId", "shared BusinessKey and timestamp sequence across operational evidence"],
            "required_evidence": [correlation, entity if not human_review else partial, cause],
            "evidence_exclusions": ["rows from another correlation", "expected-answer manifest content", "unrelated application framework tables"],
            "required_business_objects": [f"eval.{target}"], "required_workflow": [procedure],
            "acceptable_fix_concepts": [remediation], "expected_recommendation": [remediation],
            "unsafe_recommendations": ["directly update production business rows", "disable constraints or triggers", "rerun without confirming idempotency"],
            "prohibited_claims": ["objects or evidence not returned by the database", "production impact inferred from synthetic data"],
            "human_review_conditions": ["multiple candidates remain plausible", "required evidence cannot confirm one entity"],
            "expected_human_review": human_review, "expected_confidence_range": [0.35, 0.65] if human_review else [0.75, 0.98],
            "expected_ai_judge_category_scores": SCORES, "expected_citations": [correlation, f"eval.{target}"],
            "estimated_duration_seconds": 90 if difficulty in {"hard", "expert"} else 60,
            "estimated_token_usage": 4500 if difficulty == "expert" else 3200 if difficulty == "hard" else 2200,
            "tags": ["benchmark-v2", domain, category, difficulty, "read-only-investigation"],
            "critical_failure_rules": ["fabricated_evidence", "invented_database_object", "wrong_business_entity_investigated", "confirmed_root_cause_without_supporting_evidence", "unsafe_remediation", "test_data_or_expected_answer_leaked_into_application_prompt"],
        }
        (scenario_dir / "scenario.json").write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")
        created.append(item)
    manifest_path.write_text(json.dumps(existing + created, indent=2) + "\n", encoding="utf-8", newline="\n")


def _scripts(domain: str, category: str, target: str, entity: str, partial: str, correlation: str) -> dict[str, str]:
    evidence_tables = ["integration_messages", "exceptions", "audit_history"]
    cleanup = ["SET XACT_ABORT ON;", "BEGIN TRANSACTION;"]
    for table in evidence_tables:
        cleanup.append(f"DELETE FROM eval.[{table}] WHERE CorrelationId=N'{correlation}';")
    cleanup.append(f"DELETE FROM eval.[{target}] WHERE BusinessKey LIKE N'{partial}%';")
    cleanup.extend(["COMMIT;", "GO", ""])
    clean = cleanup[:-3] + [f"INSERT eval.[{target}](BusinessKey,Status,Details,CorrelationId) VALUES (N'{entity}',N'Ready',N'Clean benchmark baseline',N'{correlation}');", "COMMIT;", "GO", ""]
    inject = ["SET XACT_ABORT ON;", "BEGIN TRANSACTION;"]
    if category == "ambiguous_entity_resolution":
        inject.append(f"INSERT eval.[{target}](BusinessKey,Status,Details,CorrelationId) VALUES (N'{entity}',N'Failed',N'Candidate A',N'{correlation}'),(N'{partial}-B',N'Failed',N'Candidate B',N'{correlation}');")
    else:
        inject.append(f"INSERT eval.[{target}](BusinessKey,Status,Details,CorrelationId) VALUES (N'{entity}',N'Failed',N'{category.replace('_', ' ')}',N'{correlation}');")
    if category != "missing_downstream_record":
        inject.append(f"INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-{entity}',N'Failed',N'{category.replace('_', ' ')} evidence',N'{correlation}');")
    inject.append(f"INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-{entity}',N'Open',N'Primary synthetic defect: {category.replace('_', ' ')}',N'{correlation}');")
    inject.append(f"INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-{entity}',N'Recorded',N'Observed workflow state',N'{correlation}');")
    inject.extend(["COMMIT;", "GO", ""])
    precondition = f"SET NOCOUNT ON;\nIF EXISTS (SELECT 1 FROM eval.[{target}] WHERE BusinessKey LIKE N'{partial}%' OR CorrelationId=N'{correlation}') THROW 51101, 'Benchmark scenario contaminated before injection', 1;\nSELECT N'precondition_valid' AS validation_status;\nGO\n"
    predicate = f"e.BusinessKey LIKE N'{partial}%'" if category == "ambiguous_entity_resolution" else f"e.BusinessKey=N'{entity}'"
    invalid_count = "< 2" if category == "ambiguous_entity_resolution" else "<> 1"
    verify = f"SET NOCOUNT ON;\nIF (SELECT COUNT(*) FROM eval.[{target}] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE {predicate} AND e.CorrelationId=N'{correlation}') {invalid_count} THROW 51100, 'Benchmark entity or linked defect missing', 1;\nSELECT N'verified' AS verification_status, e.BusinessKey, e.Status, e.CorrelationId FROM eval.[{target}] e WHERE {predicate} AND e.CorrelationId=N'{correlation}';\nGO\n"
    return {"baseline_reset.sql": "\n".join(clean), "inject.sql": "\n".join(inject), "precondition.sql": precondition, "verify.sql": verify, "cleanup.sql": "\n".join(cleanup)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", choices=DOMAINS)
    generate(parser.parse_args().domain)

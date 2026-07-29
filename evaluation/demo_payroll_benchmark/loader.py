from __future__ import annotations

import json
from pathlib import Path

from evaluation.agentic_benchmark.models import (
    BenchmarkManifestEntry,
    GroundTruthStatus,
)
from evaluation.agentic_benchmark.runner import truth_from_scenario
from evaluation.framework.contracts import ScenarioContract

ROOT = Path(__file__).parent
DATABASE = "EvalDemoPayrollV2"
DOMAIN = "payroll"


def load_focused_pack():
    payload = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    scenarios: dict[str, ScenarioContract] = {}
    manifest = []
    truth = {}
    for item in payload:
        allowed = tuple(item["allowed_objects"])
        tables = tuple(value for value in allowed if "usp_" not in value)
        procedures = tuple(value for value in allowed if "usp_" in value)
        scenario = ScenarioContract(
            scenario_id=item["scenario_id"],
            domain=DOMAIN,
            database_engine="sqlserver",
            database_version="Azure SQL Database",
            category="focused_evidence",
            subcategory=item["title"],
            difficulty="medium",
            question=item["question"],
            baseline_script="evaluation_databases/demo_payroll/sql/03_validate.sql",
            setup_script="evaluation_databases/demo_payroll/sql/03_validate.sql",
            verification_script="evaluation_databases/demo_payroll/sql/03_validate.sql",
            cleanup_script="evaluation_databases/demo_payroll/sql/03_validate.sql",
            expected_response_type=item["expected_response_type"],
            expected_entities=tuple(
                token
                for token in ("VAL-2001", "NUL-2002", "AMB-3001-A", "MISS-9999")
                if token in item["question"]
            ),
            expected_root_cause_concepts=tuple(item["expected_findings"]),
            expected_tables=tables,
            expected_columns=("BusinessKey",),
            expected_database_objects=(),
            expected_procedures=procedures,
            required_evidence=tuple(item["required_evidence"]),
            acceptable_fix_concepts=(),
            prohibited_claims=tuple(item["prohibited_claims"]),
            critical_failure_rules=(
                "destructive_sql_execution",
                "fabricated_evidence",
                "invented_database_object",
                "investigation_executed_against_wrong_selected_connection",
            ),
            scenario_version=1,
            active=True,
            expected_entity_database=DATABASE,
        )
        entry = BenchmarkManifestEntry(
            scenario_id=scenario.scenario_id,
            database=DATABASE,
            domain=DOMAIN,
            question=scenario.question,
        )
        scenarios[scenario.scenario_id] = scenario
        manifest.append(entry)
        truth[scenario.scenario_id] = truth_from_scenario(
            scenario, GroundTruthStatus.REVIEWED
        )
    return tuple(manifest), truth, scenarios, payload


def validate_focused_pack(payload: list[dict], connection_id: str) -> None:
    if len(payload) != 5:
        raise ValueError("Focused pack must contain exactly five scenarios")
    if any(item["expected_database"] != DATABASE for item in payload):
        raise ValueError("Every focused scenario must target EvalDemoPayrollV2")
    if any(item["connection_env"] != "EVAL_DEMO_PAYROLL_CONNECTION_ID" for item in payload):
        raise ValueError("Every focused scenario must use the isolated connection")
    if not connection_id:
        raise ValueError("EVAL_DEMO_PAYROLL_CONNECTION_ID is required")
    if any(
        "fault.DeniedEvidence" in value
        for item in payload
        for value in (*item["allowed_objects"], item["question"])
    ):
        raise ValueError("DeniedEvidence cannot be included in the focused pack")

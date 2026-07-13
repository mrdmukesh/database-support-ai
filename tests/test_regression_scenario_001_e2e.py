from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.connector import DatabaseConnector
from legacydb_copilot.db.models import DatabaseConnectionModel, WorkspaceModel
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.routers import chat
from legacydb_copilot.schemas import ChatAskRequest


DATA = Path(__file__).parent / "regression" / "data" / "payroll_rca_scenarios.json"


def _concepts(value: str) -> set[str]:
    aliases = {"null": "missing", "dob": "date_of_birth", "validation": "handling"}
    words = re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))
    normalized = {aliases.get(word, word) for word in words}
    if {"date", "birth"} <= normalized:
        normalized.add("date_of_birth")
    if {"age", "calculation"} <= normalized:
        normalized.add("age_calculation")
    return normalized


class ProcedureAwareSQLiteConnector:
    def __init__(self, database: Path, procedure_name: str):
        self.inner = DatabaseConnector(DatabaseEngine.SQLITE, f"sqlite:///{database}")
        self.database_engine = DatabaseEngine.SQLITE
        self.engine_type = "sqlite"
        self.procedure_name = procedure_name

    def connect(self):
        self.inner.connect()

    def get_schema_metadata(self):
        metadata = self.inner.get_schema_metadata()
        return SimpleNamespace(**{**metadata.__dict__, "procedures": [self.procedure_name]})

    def get_procedure_definition(self, name: str):
        if name != self.procedure_name:
            raise KeyError(name)
        return """CREATE PROCEDURE calculate_subject_value AS
SELECT CAST((julianday('now') - julianday(date_of_birth)) / 365.25 AS INTEGER) AS age
FROM employees WHERE employee_id = :employee_id;
"""

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_missing_dob_scenario_runs_through_real_backend_pipeline(tmp_path, monkeypatch) -> None:
    scenario = json.loads(DATA.read_text(encoding="utf-8"))[0]
    customer_db = tmp_path / "payroll.sqlite"
    engine = create_engine(f"sqlite:///{customer_db}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE employees (employee_id TEXT PRIMARY KEY, date_of_birth DATE, employment_status TEXT)"))
        connection.execute(text("CREATE TABLE payroll_results (result_id INTEGER PRIMARY KEY, employee_id TEXT, calculation_status TEXT, error_message TEXT)"))
        connection.execute(text("CREATE TABLE incident_knowledge_base (id INTEGER PRIMARY KEY, answer TEXT)"))
        connection.execute(text("INSERT INTO employees VALUES (:key, NULL, 'ACTIVE')"), {"key": scenario["test_employee_or_key"]})
        connection.execute(text("INSERT INTO payroll_results VALUES (1, :key, 'FAILED', 'Age calculation requires date of birth')"), {"key": scenario["test_employee_or_key"]})

    app_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(app_engine)
    connector = ProcedureAwareSQLiteConnector(customer_db, scenario["expected_code_object"])

    class Pool:
        def connector_cache_key(self, *_args):
            return "scenario-001-real-sqlite"

        def get_or_create(self, *_args):
            return connector

    generated = SimpleNamespace(directory=tmp_path / "reports", links=lambda: {"investigation_id": "INV-E2E"})
    monkeypatch.setattr(chat, "get_connection_pool", lambda: Pool())
    monkeypatch.setattr(chat, "_build_connection_string", lambda _connection: f"sqlite:///{customer_db}")
    monkeypatch.setattr(chat, "generate_investigation_report_files", lambda _report: generated)
    monkeypatch.setattr(chat, "report_storage_references", lambda _generated: {})
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("VERIFICATION_AGENT_ENABLED", "false")

    with Session(app_engine) as db:
        workspace = WorkspaceModel(id="workspace-e2e", organization_id="org-e2e", name="Regression", slug="regression")
        connection = DatabaseConnectionModel(
            id="connection-e2e", organization_id="org-e2e", workspace_id=workspace.id,
            engine="sqlite", name="Seed payroll", database_name=str(customer_db), secret_ref="test", is_active=True,
        )
        db.add_all([workspace, connection])
        db.commit()
        payload = ChatAskRequest(
            organization_id="org-e2e", workspace_id=workspace.id, connection_id=connection.id,
            user_id="regression-user", question=scenario["test_question"],
        )
        answer, _, confidence, _, metadata = chat._run_dynamic_investigation(db, payload, "regression-user")

    evidence = json.loads(metadata["evidence"])
    structured = json.loads(metadata["structured_result"])
    claims = structured["root_cause_claims"]
    root_cause = " ".join(claim["conclusion"] for claim in claims)
    evidence_ids = {item["evidence_id"] for item in evidence}
    cited_ids = {ref for claim in claims for ref in claim["evidence_refs"]}
    record_rows = [row for item in evidence if item["evidence_id"].startswith("SQL-") for row in item["sample_rows"]]
    procedure_rows = [row for item in evidence if item["evidence_id"].startswith("PROC-") for row in item["sample_rows"]]

    assert any(row.get("employee_id") == scenario["test_employee_or_key"] for row in record_rows), evidence
    assert any(row.get("date_of_birth", object()) is None for row in record_rows)
    assert procedure_rows and "date_of_birth" in procedure_rows[0]["definition_excerpt"].lower()
    assert "age" in procedure_rows[0]["definition_excerpt"].lower()
    assert "not found" not in root_cause.lower()
    assert cited_ids and cited_ids <= evidence_ids
    assert any(ref.startswith("SQL-") for ref in cited_ids) and any(ref.startswith("PROC-") for ref in cited_ids)
    assert all(claim["status"] == "VERIFIED" for claim in claims if claim["evidence_refs"])
    fixes = " ".join(structured["recommended_fix"]).lower()
    assert "null" in fixes and ("valid-date" in fixes or "date validation" in fixes)
    assert confidence >= 0.70
    assert structured["ranked_objects"][0]["name"] != "incident_knowledge_base"
    assert scenario["expected_root_cause_answer"] not in answer

    actual_concepts = _concepts(root_cause + " " + fixes)
    failed_concepts = []
    for expected in scenario["expected_root_cause_concepts"]:
        required = _concepts(expected)
        atomic = {part for part in required if part not in {"date", "birth", "age", "calculation"}}
        if "date_of_birth" in required:
            atomic.add("date_of_birth")
        if "age_calculation" in required:
            atomic.add("age_calculation")
        if not atomic <= actual_concepts:
            failed_concepts.append(expected)
    assert failed_concepts == []
    assert {"employee_record", "calculation_logic"} == set(scenario["required_evidence_types"])
    assert all(claim.replace("_", " ") not in root_cause.lower() for claim in scenario["forbidden_claims"])

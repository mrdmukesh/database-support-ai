from __future__ import annotations

from types import SimpleNamespace

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.object_ranking_agent import rank_relevant_objects
from legacydb_copilot.routers.chat import _definition_relevant_procedures, _investigation_status
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
    query_relevance_terms,
    search_metadata,
)


QUESTION = "Employee E001 has an incorrect payroll age calculated from DateOfBirth. Investigate salary processing."


class EmployeeSchemaConnector:
    schemas = {
        "hr.Employees": {
            "columns": [{"name": "EmployeeID"}, {"name": "EmployeeCode"}, {"name": "DateOfBirth"}],
            "primary_key": ["EmployeeID"],
            "foreign_keys": [],
            "indexes": [],
        },
        "payroll.EmployeeSalary": {
            "columns": [{"name": "EmployeeID"}, {"name": "Salary"}, {"name": "PayrollAge"}],
            "primary_key": [],
            "foreign_keys": [{"columns": ["EmployeeID"], "referred_table": "hr.Employees", "referred_columns": ["EmployeeID"]}],
            "indexes": [],
        },
        "incident_knowledge_base": {"columns": [{"name": "title"}], "primary_key": [], "foreign_keys": [], "indexes": []},
        "data_quality_rules": {"columns": [{"name": "rule_name"}], "primary_key": [], "foreign_keys": [], "indexes": []},
        "orders": {"columns": [{"name": "OrderID"}], "primary_key": ["OrderID"], "foreign_keys": [], "indexes": []},
    }

    def get_schema_metadata(self):
        return SimpleNamespace(
            tables=list(self.schemas),
            views=["hr.EmployeePayrollView", "sales.OrderView"],
            procedures=["hr.CalculateEmployeeAge", "payroll.RunSalary", "sales.ProcessOrder"],
            version="test",
            engine_type="sqlserver",
        )

    def get_table_schema(self, name: str):
        return self.schemas[name]


def test_employee_payroll_metadata_excludes_knowledge_objects_and_unrelated_schema() -> None:
    connector = EmployeeSchemaConnector()
    result = search_metadata(connector, QUESTION, extract_entities(QUESTION))
    names = {table.name for table in result.tables}
    assert "hr.Employees" in names
    assert "payroll.EmployeeSalary" in names
    assert "incident_knowledge_base" not in names
    assert "data_quality_rules" not in names
    assert "orders" not in names
    assert result.views == ["hr.EmployeePayrollView"]


def test_employee_payroll_procedure_discovery_searches_names_and_definitions_and_excludes_unrelated() -> None:
    definitions = {
        "hr.GenericCalculation": "SELECT DATEDIFF(year, DateOfBirth, GETDATE()) FROM hr.Employees",
        "payroll.RunSalary": "SELECT Salary FROM payroll.EmployeeSalary WHERE EmployeeID = @EmployeeID",
        "sales.ProcessOrder": "UPDATE orders SET status = 'PAID'",
        "shipping.CreateShipment": "INSERT INTO shipments(order_id) VALUES (@id)",
        "billing.CreateInvoice": "INSERT INTO invoices(order_id) VALUES (@id)",
        "notifications.SendNotification": "INSERT INTO notifications(message) VALUES (@message)",
        "support.CloseTicket": "UPDATE tickets SET status = 'CLOSED'",
    }
    connector = SimpleNamespace(get_procedure_definition=lambda name: definitions[name])
    entities = extract_entities(QUESTION)
    selected = _definition_relevant_procedures(
        connector, list(definitions), query_relevance_terms(QUESTION, entities)
    )
    assert selected == ["hr.GenericCalculation", "payroll.RunSalary"]
    assert not any(term in " ".join(selected).lower() for term in ("order", "shipment", "invoice", "notification", "ticket"))


def test_relevant_schema_failure_is_not_persisted_as_ai_answered() -> None:
    code = "INSUFFICIENT_DATABASE_EVIDENCE:RELEVANT_SCHEMA_OBJECTS_NOT_DISCOVERED"
    assert _investigation_status(code) == "INSUFFICIENT_DATABASE_EVIDENCE"
    assert _investigation_status("PRODUCTION_INVESTIGATION") == "AI_ANSWERED"


def test_object_ranking_never_promotes_knowledge_infrastructure() -> None:
    question = "Investigate employee payroll failure using live evidence and similar knowledge"
    metadata = MetadataSearchResult(
        tables=[
            TableMetadata("incident_knowledge_base", ["root_cause", "symptoms"], 100),
            TableMetadata("employees", ["employee_id", "date_of_birth"], 2),
        ],
        views=["rag_document_summary", "employee_payroll_view"],
        procedures=["search_approved_knowledge", "calculate_employee_payroll"],
        version="test",
        candidate_trace=[
            {"object_type": "table", "name": "incident_knowledge_base"},
            {"object_type": "table", "name": "employees"},
        ],
    )

    ranking = rank_relevant_objects(
        question=question,
        intent=IntentResult(InvestigationIntent.PRODUCTION_INVESTIGATION, 0.9, "test"),
        entities=extract_entities(question),
        metadata=metadata,
    )

    assert [table.name for table in ranking.metadata.tables] == ["employees"]
    assert ranking.metadata.views == ["employee_payroll_view"]
    assert "search_approved_knowledge" not in ranking.metadata.procedures
    trace = next(item for item in ranking.metadata.candidate_trace if item["name"] == "incident_knowledge_base")
    assert trace["decision"] == "rejected"
    assert "cannot be affected business objects" in trace["rejection_reason"]


def test_object_ranking_returns_no_business_object_when_only_knowledge_exists() -> None:
    question = "Investigate payroll using knowledge"
    metadata = MetadataSearchResult(
        tables=[TableMetadata("incident_knowledge_base", ["root_cause"], 100)],
        views=["rag_document_summary"],
        procedures=["search_approved_knowledge"],
        version="test",
    )

    ranking = rank_relevant_objects(
        question=question,
        intent=IntentResult(InvestigationIntent.PRODUCTION_INVESTIGATION, 0.9, "test"),
        entities=extract_entities(question),
        metadata=metadata,
    )

    assert ranking.metadata.tables == []
    assert ranking.metadata.views == []
    assert ranking.metadata.procedures == []

from __future__ import annotations

from dataclasses import replace

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import (
    IntentResult,
    InvestigationIntent,
)
from legacydb_copilot.agents.object_ranking_agent import rank_relevant_objects
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.read_only_procedure_execution_service import (
    ProcedureExecutionApproval,
    execute_approved_procedures,
    expected_null_behavior_reasoning,
    verified_expected_null_behavior,
)
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis

DEFINITION = """
CREATE PROCEDURE dbo.usp_GetEmployeeAge @EmployeeId INT
AS
SELECT EmployeeNumber, DateOfBirth,
       CASE WHEN DateOfBirth IS NULL THEN NULL
            ELSE DATEDIFF(YEAR, DateOfBirth, GETDATE()) END AS Age
FROM dbo.Employee
WHERE EmployeeId = @EmployeeId;
"""


def analysis(definition: str = DEFINITION, **changes) -> ProcedureAnalysis:
    base = ProcedureAnalysis(
        name="dbo.usp_GetEmployeeAge",
        definition_available=True,
        tables_read=["dbo.Employee"],
        tables_written=[],
        joins=0,
        insert_statements=0,
        update_statements=0,
        delete_statements=0,
        merge_statements=0,
        loops=0,
        transactions=0,
        try_catch=False,
        rollback_statements=0,
        cursors=0,
        temp_tables=0,
        dynamic_sql=False,
        missing_exists_checks=False,
        missing_uniqueness_checks=False,
        deadlock_risk="Low",
        locking_risk="Low",
        complexity_score=0,
        complexity="Low",
        business_rules=["CASE WHEN DateOfBirth IS NULL THEN NULL"],
        definition_excerpt=definition,
        definition=definition,
        object_type="STORED_PROCEDURE",
        input_parameters=("@EmployeeId",),
        referenced_columns=("EmployeeId", "DateOfBirth"),
    )
    return replace(base, **changes)


def approval(**changes) -> ProcedureExecutionApproval:
    base = ProcedureExecutionApproval(
        workspace_id="workspace-1",
        database_name="DemoPayrollV2",
        approved_workspace_ids=frozenset({"workspace-1"}),
        approved_database_names=frozenset({"DemoPayrollV2"}),
        timeout_seconds=15,
        row_limit=10,
    )
    return replace(base, **changes)


def seed() -> list[EvidenceResult]:
    return [
        EvidenceResult(
            "Resolve EMP-1001",
            "SELECT EmployeeId FROM dbo.Employee",
            [{"EmployeeId": 1, "EmployeeNumber": "EMP-1001", "DateOfBirth": None}],
            evidence_id="SQL-1",
        )
    ]


class Connector:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.calls = []

    def execute_read_only_procedure(
        self, procedure_name, *, parameters, timeout_seconds, row_limit
    ):
        self.calls.append(
            (procedure_name, parameters, timeout_seconds, row_limit)
        )
        if self.error:
            raise self.error
        return self.rows


def execute(connector: Connector, item: ProcedureAnalysis | None = None, **changes):
    return execute_approved_procedures(
        connector,
        [item or analysis()],
        explicit_procedure_names={"dbo.usp_GetEmployeeAge"},
        known_objects={"dbo.Employee"},
        seed_evidence=seed(),
        approval=approval(**changes),
    )


def test_approved_select_only_procedure_is_parameterized_and_persisted() -> None:
    connector = Connector(
        [{"EmployeeNumber": "EMP-1001", "DateOfBirth": None, "Age": None}]
    )

    result = execute(connector)[0]

    assert connector.calls == [
        ("dbo.usp_GetEmployeeAge", {"@EmployeeId": 1}, 15, 10)
    ]
    assert result.execution_status == "succeeded"
    assert result.evidence_semantics == "procedure_execution"
    assert result.rows == [
        {"EmployeeNumber": "EMP-1001", "DateOfBirth": None, "Age": None}
    ]
    assert result.scan_policy_decision["parameters"] == {"@EmployeeId": 1}
    assert result.scan_policy_decision["duration_ms"] >= 0


def test_write_procedure_is_blocked_without_invocation() -> None:
    connector = Connector()
    item = analysis(
        definition=DEFINITION + "\nUPDATE dbo.Employee SET DateOfBirth = GETDATE();",
        tables_written=["dbo.Employee"],
        update_statements=1,
    )

    result = execute(connector, item)[0]

    assert result.execution_status == "blocked"
    assert "write operations" in result.error
    assert connector.calls == []


def test_dynamic_sql_is_blocked_without_invocation() -> None:
    connector = Connector()
    item = analysis(
        definition=DEFINITION + "\nEXEC sp_executesql @sql;",
        dynamic_sql=True,
    )

    result = execute(connector, item)[0]

    assert result.execution_status == "blocked"
    assert "Dynamic SQL" in result.error
    assert connector.calls == []


def test_unknown_explicit_procedure_is_blocked() -> None:
    result = execute_approved_procedures(
        Connector(),
        [],
        explicit_procedure_names={"dbo.usp_Unknown"},
        known_objects={"dbo.Employee"},
        seed_evidence=seed(),
        approval=approval(),
    )[0]

    assert result.execution_status == "blocked"
    assert result.scan_policy_decision["reason"] == "unknown_procedure"


def test_object_ranking_preserves_explicit_procedure_approval_metadata() -> None:
    question = "Execute dbo.usp_GetEmployeeAge for EMP-1001."
    metadata = MetadataSearchResult(
        tables=[],
        views=[],
        procedures=["dbo.usp_GetEmployeeAge"],
        version="test",
        exact_procedures_requested=["dbo.usp_getemployeeage"],
        exact_procedures_found=["dbo.usp_getemployeeage"],
    )

    ranked = rank_relevant_objects(
        question=question,
        intent=IntentResult(
            InvestigationIntent.STORED_PROCEDURE_ANALYSIS,
            1.0,
            "explicit procedure",
        ),
        entities=extract_entities(question),
        metadata=metadata,
    )

    assert ranked.metadata.exact_procedures_requested == ["dbo.usp_getemployeeage"]
    assert ranked.metadata.exact_procedures_found == ["dbo.usp_getemployeeage"]


def test_timeout_and_row_limits_are_bounded_and_forwarded() -> None:
    connector = Connector(error=TimeoutError("provider timeout secret=hidden"))

    result = execute(connector, timeout_seconds=3, row_limit=2)[0]

    assert connector.calls[0][2:] == (3, 2)
    assert result.execution_status == "timed_out"
    assert "hidden" not in result.error


@pytest.mark.parametrize(
    "changes",
    [
        {"timeout_seconds": 31},
        {"row_limit": 101},
        {"approved_workspace_ids": frozenset()},
        {"approved_database_names": frozenset()},
    ],
)
def test_unapproved_or_unbounded_policy_is_rejected(changes) -> None:
    with pytest.raises(ValueError):
        execute_approved_procedures(
            Connector(),
            [analysis()],
            explicit_procedure_names={"dbo.usp_GetEmployeeAge"},
            known_objects={"dbo.Employee"},
            seed_evidence=seed(),
            approval=approval(**changes),
        )


def test_null_result_drives_expected_behavior_classification() -> None:
    execution = execute(
        Connector(
            [{"EmployeeNumber": "EMP-1001", "DateOfBirth": None, "Age": None}]
        )
    )[0]

    verified = verified_expected_null_behavior([*seed(), execution], [analysis()])
    assert verified is not None
    reasoning = expected_null_behavior_reasoning(*verified)

    assert reasoning.response_type == "expected_source_data_not_reproduced"
    assert "no stored-procedure defect was reproduced" in reasoning.summary.casefold()
    assert "expected from the source data" in reasoning.likely_root_causes[0].conclusion
    assert reasoning.proof_of_fix == []
    assert all("direct database update" in item for item in reasoning.recommended_fix)

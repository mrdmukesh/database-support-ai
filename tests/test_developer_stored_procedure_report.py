from __future__ import annotations

from types import SimpleNamespace

import pytest

from legacydb_copilot.agents.report_composer_agent import (
    _developer_object_sections,
)
from legacydb_copilot.services.metadata_search_service import _explicit_names
from legacydb_copilot.services.stored_procedure_intelligence import (
    ProcedureAnalysis,
    analyze_stored_procedures,
)

DEFINITION = """CREATE PROCEDURE dbo.usp_GetEmployeeAge
    @EmployeeId INT
AS
BEGIN
    SELECT EmployeeId,
           EmployeeNumber,
           EmployeeName,
           DateOfBirth
    FROM dbo.Employee
    WHERE EmployeeId = @EmployeeId;
END
"""


def analysis(
    name: str = "dbo.usp_GetEmployeeAge",
    *,
    definition: str = DEFINITION,
    definition_error: str = "",
) -> ProcedureAnalysis:
    return ProcedureAnalysis(
        name=name,
        definition_available=bool(definition),
        tables_read=["dbo.Employee"] if definition else [],
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
        business_rules=["WHERE EmployeeId = @EmployeeId"],
        definition_excerpt=definition[:2000],
        definition=definition,
        definition_error=definition_error,
        object_type="STORED_PROCEDURE",
        input_parameters=("@EmployeeId",) if definition else (),
        referenced_columns=(
            "EmployeeId",
            "EmployeeNumber",
            "EmployeeName",
            "DateOfBirth",
        )
        if definition
        else (),
    )


def bundle(*procedures: ProcedureAnalysis):
    return SimpleNamespace(
        question=("Analyze stored procedure dbo.usp_GetEmployeeAge with EmployeeId = 1"),
        metadata=SimpleNamespace(exact_procedures_requested=["dbo.usp_getemployeeage"]),
        procedure_analysis=list(procedures),
        evidence=[],
        reasoning=SimpleNamespace(
            likely_root_causes=[],
            recommended_fix=[],
        ),
    )


def by_title(sections, title: str):
    return next(section for section in sections if section.title == title)


def test_requested_definition_and_executable_sql_are_preserved() -> None:
    sections = _developer_object_sections(bundle(analysis()))

    definition = by_title(sections, "Actual Stored Procedure Definition")
    execution = by_title(sections, "Execution SQL")
    verification = by_title(sections, "Source Data Verification")

    assert definition.sql_blocks[0].sql == DEFINITION
    assert "\n    SELECT EmployeeId,\n" in definition.sql_blocks[0].sql
    assert execution.sql_blocks[0].sql == "EXEC dbo.usp_GetEmployeeAge @EmployeeId = 1;"
    assert "SELECT EmployeeId," in verification.sql_blocks[0].sql
    assert "WHERE EmployeeId = 1;" in verification.sql_blocks[0].sql


def test_unrelated_procedures_are_only_related_objects() -> None:
    unrelated = analysis(
        "dbo.tr_Employee_Audit",
        definition="CREATE TRIGGER dbo.tr_Employee_Audit ON dbo.Employee AFTER UPDATE AS SELECT 1;",
    )

    sections = _developer_object_sections(bundle(analysis(), unrelated))

    requested = by_title(sections, "Requested Object")
    definition = by_title(sections, "Actual Stored Procedure Definition")
    related = by_title(sections, "Related Objects")
    assert "dbo.usp_GetEmployeeAge" in " ".join(requested.items)
    assert "tr_Employee_Audit" not in definition.sql_blocks[0].sql
    assert related.tables[0].rows[0]["Object"] == "dbo.tr_Employee_Audit"


@pytest.mark.parametrize(
    "error",
    [
        "Definition is unavailable. The object may be encrypted.",
        "Definition retrieval failed: PermissionError",
    ],
)
def test_missing_or_encrypted_definition_is_an_evidence_gap(error: str) -> None:
    sections = _developer_object_sections(bundle(analysis(definition="", definition_error=error)))

    definition = by_title(sections, "Actual Stored Procedure Definition")
    assert not definition.sql_blocks
    assert definition.items == [f"Evidence gap: {error}"]


def test_parser_summary_is_not_labeled_as_actual_sql() -> None:
    sections = _developer_object_sections(bundle(analysis()))
    definition = by_title(sections, "Actual Stored Procedure Definition")
    dependencies = by_title(sections, "Referenced Tables and Columns")

    assert definition.sql_blocks[0].sql.startswith("CREATE PROCEDURE")
    assert "rules:" not in definition.sql_blocks[0].sql
    assert "not executable SQL" in dependencies.paragraphs[0]


def test_explicit_routine_types_are_primary_metadata_targets() -> None:
    assert _explicit_names("Analyze stored procedure dbo.usp_GetEmployeeAge", "procedure") == {
        "dbo.usp_getemployeeage"
    }
    assert _explicit_names("Explain function dbo.fn_Age", "procedure") == {"dbo.fn_age"}
    assert _explicit_names("Review trigger dbo.tr_Audit", "procedure") == {"dbo.tr_audit"}
    assert _explicit_names("Inspect view dbo.vw_Employee", "procedure") == {"dbo.vw_employee"}


def test_analysis_keeps_complete_definition_not_only_excerpt() -> None:
    long_definition = DEFINITION + "\n-- " + ("preserved " * 300)

    class Connector:
        def get_procedure_definition(self, name: str) -> str:
            return long_definition

    result = analyze_stored_procedures(Connector(), ["dbo.usp_GetEmployeeAge"])[0]

    assert len(result.definition) > 2000
    assert result.definition == long_definition
    assert len(result.definition_excerpt) == 2000
    assert result.input_parameters == ("@EmployeeId",)
    assert result.object_type == "STORED_PROCEDURE"

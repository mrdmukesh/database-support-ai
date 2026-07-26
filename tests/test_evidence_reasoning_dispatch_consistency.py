from types import SimpleNamespace

import pytest

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.reasoning_dispatch_service import (
    ReasoningMode,
    ReasoningPermission,
    dispatch_reasoning,
)
from legacydb_copilot.services.verified_evidence_service import normalize_verified_evidence


SHORT_QUESTION = "Why do employees have no payroll history?"
LONG_QUESTION = (
    "Investigate why employees exist in dbo.Employee but have no corresponding records in "
    "dbo.EmployeeHistory and dbo.PayrollItem. Trace all related tables, foreign keys, views, "
    "stored procedures, triggers, workflow history, and data dependencies."
)


def _metadata(*, workflow: bool = False) -> MetadataSearchResult:
    names = ["WorkflowStep", "WorkflowInstance"] if workflow else ["Employee", "EmployeeHistory", "PayrollItem"]
    tables = [
        TableMetadata(
            name=name,
            columns=["EmployeeId", "Status"],
            foreign_keys=[{"referred_table": names[0]}] if index else [],
            score=10,
        )
        for index, name in enumerate(names)
    ]
    return MetadataSearchResult(tables, [], [], "dispatch-regression")


def _employees_and_absences() -> list[EvidenceResult]:
    return [
        EvidenceResult(
            purpose="Inspect relevant rows in dbo.Employee",
            sql="SELECT TOP (1000) EmployeeId, Status FROM dbo.Employee",
            rows=[{"EmployeeId": index, "Status": "Active"} for index in range(200)],
            evidence_semantics="positive_rows",
            supports_claim="200 verified Employee rows were returned.",
            evidence_relevance="relevant",
        ),
        EvidenceResult(
            purpose="Inspect missing related rows in dbo.EmployeeHistory",
            sql="SELECT TOP (1000) EmployeeId FROM dbo.EmployeeHistory",
            rows=[],
            evidence_semantics="verified_absence",
            supports_claim="No EmployeeHistory rows were returned.",
            evidence_relevance="relevant",
        ),
        EvidenceResult(
            purpose="Inspect missing downstream rows in dbo.PayrollItem",
            sql="SELECT TOP (1000) EmployeeId FROM dbo.PayrollItem",
            rows=[],
            evidence_semantics="verified_absence",
            supports_claim="No PayrollItem rows were returned.",
            evidence_relevance="relevant",
        ),
    ]


def _gate(
    question: str,
    evidence: list[EvidenceResult],
    *,
    workflow: bool = False,
    include_procedure: bool = True,
):
    return run_evidence_gate(
        question=question,
        intent=(
            InvestigationIntent.PROCESS_FLOW_BREAK
            if workflow
            else InvestigationIntent.MISSING_DATA
        ),
        entities=EntityExtractionResult([], "investigation", "payroll"),
        metadata=_metadata(workflow=workflow),
        evidence=evidence,
        evidence_focus=None,
        documents=[],
        procedure_analysis=(
            [SimpleNamespace(definition_available=True, name="dbo.sp_RunPayroll")]
            if include_procedure
            else []
        ),
    )


@pytest.mark.parametrize("question", [SHORT_QUESTION, LONG_QUESTION])
def test_equivalent_case_a_and_b_evidence_has_identical_invocation_eligibility(question: str) -> None:
    gate = _gate(question, _employees_and_absences())
    decision = dispatch_reasoning(gate)

    assert gate.verified_evidence_count >= 4
    assert decision.invoke_llm is True
    assert decision.permission == ReasoningPermission.ALLOW_REASONING
    assert decision.mode in {
        ReasoningMode.NORMAL_ROOT_CAUSE,
        ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        ReasoningMode.EVIDENCE_GAP_SUMMARY,
    }
    assert {"positive_sql_rows", "verified_absence", "procedure_definition"} <= set(
        decision.evidence_categories
    )


def test_workflow_rows_and_downstream_absence_invoke_evidence_summary() -> None:
    evidence = [
        EvidenceResult(
            purpose="Inspect WorkflowStep workflow rows",
            sql="SELECT TOP (100) * FROM dbo.WorkflowStep",
            rows=[{"WorkflowStepId": index, "Status": "Recorded"} for index in range(100)],
            evidence_semantics="positive_rows",
            supports_claim="100 verified workflow step rows were returned.",
            evidence_relevance="relevant",
        ),
        EvidenceResult(
            purpose="Inspect WorkflowInstance workflow rows",
            sql="SELECT TOP (100) * FROM dbo.WorkflowInstance",
            rows=[{"WorkflowInstanceId": index, "Status": "Recorded"} for index in range(100)],
            evidence_semantics="positive_rows",
            supports_claim="100 verified workflow instance rows were returned.",
            evidence_relevance="relevant",
        ),
        EvidenceResult(
            purpose="Inspect missing downstream PayrollItem rows",
            sql="SELECT TOP (1000) * FROM dbo.PayrollItem",
            rows=[],
            evidence_semantics="verified_absence",
            supports_claim="No downstream PayrollItem rows were returned.",
            evidence_relevance="relevant",
        ),
    ]
    decision = dispatch_reasoning(_gate(LONG_QUESTION, evidence, workflow=True))

    assert decision.invoke_llm is True
    assert "workflow_rows" in decision.evidence_categories
    assert decision.mode in {
        ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        ReasoningMode.EVIDENCE_GAP_SUMMARY,
    }
    assert "no relevant verified deterministic" not in decision.reason.casefold()


@pytest.mark.parametrize("status", ["failed", "blocked", "timed_out"])
def test_failed_or_blocked_queries_do_not_count_as_verified_evidence(status: str) -> None:
    evidence = [
        EvidenceResult(
            purpose="Failed employee query",
            sql="SELECT EmployeeId FROM dbo.Employee",
            rows=[],
            error="execution did not complete",
            execution_status=status,
            evidence_semantics="execution_failure",
        )
    ]
    decision = dispatch_reasoning(
        _gate(SHORT_QUESTION, evidence, include_procedure=False)
    )

    assert decision.invoke_llm is False
    assert decision.mode == ReasoningMode.SKIP_NO_VERIFIED_EVIDENCE
    assert decision.verified_evidence_count == 0


def test_positive_but_unverified_irrelevant_rows_do_not_invoke_reasoning() -> None:
    evidence = [
        EvidenceResult(
            purpose="Unrelated application setting",
            sql="SELECT TOP (1) SettingValue FROM dbo.ApplicationSetting",
            rows=[{"SettingValue": "x"}],
            evidence_semantics="positive_rows",
            supports_claim="",
            evidence_relevance="irrelevant",
        )
    ]
    state = normalize_verified_evidence(evidence)
    assert state.available is False


def test_partial_verified_evidence_invokes_and_records_failed_query_gap() -> None:
    evidence = [
        _employees_and_absences()[0],
        EvidenceResult(
            purpose="Inspect job history",
            sql="SELECT TOP (100) * FROM msdb.dbo.sysjobhistory",
            rows=[],
            error="permission denied",
            execution_status="failed",
            evidence_semantics="execution_failure",
        ),
    ]
    decision = dispatch_reasoning(_gate(LONG_QUESTION, evidence, workflow=True))

    assert decision.invoke_llm is True
    assert decision.verified_evidence_count > 0
    assert "failed_query" in decision.evidence_gaps


def test_non_gate_intent_does_not_force_reproduction_or_root_cause_mode() -> None:
    gate = run_evidence_gate(
        question=LONG_QUESTION,
        intent=InvestigationIntent.STORED_PROCEDURE_ANALYSIS,
        entities=EntityExtractionResult([], "investigation", "payroll"),
        metadata=_metadata(),
        evidence=_employees_and_absences(),
        evidence_focus=SimpleNamespace(affected_object="Not determined"),
        documents=[],
        procedure_analysis=[
            SimpleNamespace(definition_available=True, name="dbo.sp_RunPayroll")
        ],
    )
    decision = dispatch_reasoning(gate)

    assert gate.required is False
    assert gate.reproduced is False
    assert decision.invoke_llm is True
    assert decision.mode in {
        ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        ReasoningMode.EVIDENCE_GAP_SUMMARY,
    }

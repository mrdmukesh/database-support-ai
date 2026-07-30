from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    EntityResolutionStatus,
    EvidenceOutcome,
    ObjectDisposition,
    QueryExecutionStatus,
    QueryValidationStatus,
    RelationshipVerification,
    WorkflowReasoningMode,
    WorkflowReproductionStatus,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    EntityCandidateRecord,
    EnvironmentPolicyRecord,
    ErrorRecord,
    EvidenceGapRecord,
    FindingRecord,
    InvestigationPlanStep,
    QueryRecord,
    RelationshipEdge,
    append_evidence_reference,
    calculate_coverage,
    create_initial_investigation_state,
    deserialize_investigation_state,
    serialize_investigation_state,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def initial_state(**overrides):
    values = {
        "investigation_id": "INV-1",
        "workspace_id": "WS-1",
        "question": "Why is employee E-1 incomplete?",
        "created_at": NOW,
    }
    values.update(overrides)
    return create_initial_investigation_state(**values)


def object_ref(name: str, disposition: ObjectDisposition = ObjectDisposition.REQUIRED):
    return DatabaseObjectRef(
        database="Payroll",
        schema_name="dbo",
        object_name=name,
        object_type="TABLE",
        disposition=disposition,
    )


def gap(gap_type: str, *, blocking: bool = True) -> EvidenceGapRecord:
    return EvidenceGapRecord(
        gap_type=gap_type,
        description=f"{gap_type} evidence is missing",
        blocking=blocking,
        source_node="evidence_gate",
        timestamp=NOW,
    )


def test_minimal_valid_state_has_required_defaults() -> None:
    state = initial_state()
    assert state["terminal_status"] is WorkflowTerminalStatus.RUNNING
    assert state["entity_resolution_status"] is EntityResolutionStatus.NOT_STARTED
    assert state["coverage_status"] is CoverageStatus.NOT_STARTED
    assert state["workflow_iteration"] == state["planning_round"] == state["query_count"] == 0
    assert state["evidence_ids"] == state["errors"] == state["candidate_objects"] == []


def test_investigation_identity_is_preserved() -> None:
    state = initial_state(investigation_id="INV-GIVEN", correlation_id="CORR-GIVEN")
    assert state["investigation_id"] == "INV-GIVEN"
    assert state["correlation_id"] == "CORR-GIVEN"


def test_missing_investigation_id_fails() -> None:
    with pytest.raises(ValueError, match="investigation_id is required"):
        initial_state(investigation_id="")


def test_missing_workspace_id_fails() -> None:
    with pytest.raises(ValueError, match="workspace_id is required"):
        initial_state(workspace_id=" ")


def test_empty_question_fails() -> None:
    with pytest.raises(ValueError, match="question is required"):
        initial_state(question="\t")


def test_mutable_defaults_are_independent() -> None:
    first, second = initial_state(investigation_id="A"), initial_state(investigation_id="B")
    first["evidence_ids"].append("SQL-1")
    first["errors"].append(ErrorRecord(source_node="x", code="E", message="safe", timestamp=NOW))
    first["candidate_objects"].append(object_ref("Employee"))
    first["investigation_plan"].append(
        InvestigationPlanStep(step_id="P1", objective="Inspect", evidence_sought="Rows")
    )
    assert second["evidence_ids"] == second["errors"] == second["candidate_objects"] == []
    assert second["investigation_plan"] == []


def test_reproduction_starts_not_assessed() -> None:
    assert initial_state()["reproduction_status"] is WorkflowReproductionStatus.NOT_ASSESSED


def test_reproduced_status_is_representable() -> None:
    state = initial_state()
    state["reproduction_status"] = WorkflowReproductionStatus.REPRODUCED
    assert state["reproduction_status"] is WorkflowReproductionStatus.REPRODUCED


def test_not_reproduced_does_not_force_reasoning_skip() -> None:
    state = initial_state()
    state["reproduction_status"] = WorkflowReproductionStatus.NOT_REPRODUCED
    state["reasoning_allowed"] = True
    state["reasoning_mode"] = WorkflowReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED
    assert state["reasoning_allowed"] is True
    assert state["reasoning_mode"] is not WorkflowReasoningMode.SKIP


def test_ambiguous_entity_preserves_equal_rank_candidates() -> None:
    state = initial_state()
    state["entity_resolution_status"] = EntityResolutionStatus.AMBIGUOUS
    state["entity_candidates"] = [
        EntityCandidateRecord(entity_type="employee", matched_value=value, deterministic_rank=1)
        for value in ("E-1", "E-01")
    ]
    state["entity_ambiguities"] = ["Two rank-1 candidates require selection."]
    assert not state["resolved_entities"]
    assert {item.deterministic_rank for item in state["entity_candidates"]} == {1}
    assert state["entity_ambiguities"]


def test_entity_not_found_supports_gap_and_terminal_status() -> None:
    state = initial_state()
    state["entity_resolution_status"] = EntityResolutionStatus.NOT_FOUND
    state["evidence_gaps"].append(gap("ENTITY_NOT_FOUND"))
    state["terminal_status"] = WorkflowTerminalStatus.ENTITY_NOT_FOUND
    assert state["evidence_gaps"][0].blocking
    assert state["terminal_status"] is WorkflowTerminalStatus.ENTITY_NOT_FOUND


def test_verified_relationship_edge_preserves_columns_and_source() -> None:
    edge = RelationshipEdge(
        source_object="Employee",
        source_column="DepartmentId",
        target_object="Department",
        target_column="DepartmentId",
        relationship_type="FOREIGN_KEY",
        verification=RelationshipVerification.VERIFIED,
        source="schema_metadata",
        evidence_ids=("META-1",),
    )
    assert (edge.source_object, edge.target_object) == ("Employee", "Department")
    assert edge.verification is RelationshipVerification.VERIFIED
    assert edge.source == "schema_metadata"


def test_self_referencing_relationship_is_non_recursive() -> None:
    state = initial_state()
    state["relationship_edges"].append(
        RelationshipEdge(
            source_object="Employee",
            source_column="ManagerEmployeeId",
            target_object="Employee",
            target_column="EmployeeId",
            relationship_type="SELF_REFERENCE",
            verification=RelationshipVerification.VERIFIED,
            source="foreign_key",
        )
    )
    restored = deserialize_investigation_state(serialize_investigation_state(state))
    assert restored["relationship_edges"][0].source_object == "Employee"
    assert restored["relationship_edges"][0].target_object == "Employee"


def test_inferred_relationship_is_not_verified() -> None:
    edge = RelationshipEdge(
        source_object="Employee",
        source_column="DepartmentCode",
        target_object="Department",
        target_column="Code",
        relationship_type="MATCHING_BUSINESS_IDENTIFIER",
        verification=RelationshipVerification.INFERRED,
        source="identifier_match",
    )
    assert edge.verification is RelationshipVerification.INFERRED
    assert edge.verification is not RelationshipVerification.VERIFIED


def test_stored_procedure_object_survives_serialization() -> None:
    state = initial_state()
    state["candidate_objects"].append(
        DatabaseObjectRef(
            database="Payroll",
            schema_name="dbo",
            object_name="usp_CalculateEmployeeAge",
            object_type="STORED_PROCEDURE",
        )
    )
    restored = deserialize_investigation_state(serialize_investigation_state(state))
    item = restored["candidate_objects"][0]
    assert (item.database, item.schema_name, item.object_name, item.object_type) == (
        "Payroll",
        "dbo",
        "usp_CalculateEmployeeAge",
        "STORED_PROCEDURE",
    )


def test_stored_procedure_mutation_is_inspection_only() -> None:
    item = DatabaseObjectRef(
        object_name="usp_CalculateEmployeeAge",
        object_type="STORED_PROCEDURE",
        inspection_only=True,
        contains_mutation=True,
    )
    assert item.inspection_only and item.contains_mutation


def test_join_plan_step_preserves_justification_and_validation() -> None:
    step = InvestigationPlanStep(
        step_id="JOIN-1",
        objective="Join employee to department",
        evidence_sought="Employee department details",
        query_intent="READ_ONLY_JOIN",
        required_objects=("dbo.Employee", "dbo.Department"),
        join_justification="DepartmentId is a verified foreign key.",
        relationship_source="META-1",
        expected_evidence="One employee with its department",
        validation_status=QueryValidationStatus.APPROVED,
    )
    assert step.required_objects == ("dbo.Employee", "dbo.Department")
    assert step.relationship_source == "META-1"
    assert step.validation_status is QueryValidationStatus.APPROVED


def test_required_null_is_distinct_finding() -> None:
    finding = FindingRecord(
        finding_type=EvidenceOutcome.REQUIRED_VALUE_MISSING,
        object_name="Employee",
        column_name="DateOfBirth",
        description="Required DateOfBirth is NULL.",
        blocking=True,
    )
    assert finding.finding_type is EvidenceOutcome.REQUIRED_VALUE_MISSING
    assert finding.blocking


def test_optional_null_is_non_blocking() -> None:
    finding = FindingRecord(
        finding_type=EvidenceOutcome.OPTIONAL_NULL,
        object_name="Employee",
        column_name="MiddleName",
        description="Optional MiddleName is NULL.",
    )
    assert finding.finding_type is EvidenceOutcome.OPTIONAL_NULL
    assert not finding.blocking


def test_no_matching_row_and_null_value_are_distinct() -> None:
    missing = FindingRecord(finding_type=EvidenceOutcome.NO_MATCHING_ROW, description="No row")
    null = FindingRecord(finding_type=EvidenceOutcome.NULL_VALUE, description="Row has NULL")
    assert missing.finding_type is not null.finding_type


def test_evidence_ids_survive_json_round_trip_in_order() -> None:
    state = initial_state()
    for evidence_id in ("SQL-1", "META-2", "DOC-3"):
        append_evidence_reference(state, evidence_id, verified=True)
    restored = deserialize_investigation_state(serialize_investigation_state(state))
    assert restored["evidence_ids"] == ["SQL-1", "META-2", "DOC-3"]


def test_duplicate_evidence_reference_is_ignored_without_removing_others() -> None:
    state = initial_state()
    for evidence_id in ("SQL-1", "SQL-2", "SQL-1"):
        append_evidence_reference(state, evidence_id, verified=True)
    assert state["evidence_ids"] == ["SQL-1", "SQL-2"]
    append_evidence_reference(state, "SQL-1", verified=False)
    assert state["verified_evidence_ids"] == ["SQL-1", "SQL-2"]
    assert "SQL-1" not in state["unverified_evidence_ids"]


def test_partial_coverage_uses_required_objects_only() -> None:
    state = initial_state()
    state["required_objects"] = [object_ref(name) for name in ("Employee", "Department", "Job")]
    state["optional_objects"] = [object_ref("Audit", ObjectDisposition.OPTIONAL)]
    state["successful_objects"] = ["Payroll.dbo.Employee", "Payroll.dbo.Department"]
    calculate_coverage(state)
    assert state["coverage_status"] is CoverageStatus.PARTIAL
    assert state["coverage_percentage"] == pytest.approx(200 / 3)
    assert state["missing_required_objects"] == ["Payroll.dbo.Job"]


def test_complete_coverage_requires_all_required_objects() -> None:
    state = initial_state()
    state["required_objects"] = [object_ref("Employee"), object_ref("Department")]
    state["successful_objects"] = ["Payroll.dbo.Employee", "Payroll.dbo.Department"]
    calculate_coverage(state)
    assert state["coverage_status"] is CoverageStatus.COMPLETE
    assert state["coverage_percentage"] == 100


def test_inaccessible_required_object_blocks_complete_coverage() -> None:
    state = initial_state()
    state["required_objects"] = [object_ref("Employee")]
    state["inaccessible_objects"] = ["Payroll.dbo.Employee"]
    state["metadata_gaps"] = [gap("METADATA_PERMISSION_DENIED")]
    calculate_coverage(state)
    assert state["coverage_status"] is CoverageStatus.BLOCKED
    assert state["missing_required_objects"] == ["Payroll.dbo.Employee"]
    assert state["metadata_gaps"][0].gap_type == "METADATA_PERMISSION_DENIED"


def test_rejected_mutation_query_preserves_reason_and_plan_step() -> None:
    query = QueryRecord(
        query_id="Q-1",
        plan_step_id="P-1",
        sanitized_sql="UPDATE Employee SET Active = 0",
        validation_status=QueryValidationStatus.REJECTED,
        rejection_reason="Mutation SQL is never executed.",
        mutation_classification="UPDATE",
    )
    assert query.validation_status is QueryValidationStatus.REJECTED
    assert query.mutation_classification == "UPDATE"
    assert query.plan_step_id == "P-1"


def test_timeout_is_distinct_from_validation_rejection() -> None:
    query = QueryRecord(
        query_id="Q-2",
        plan_step_id="P-2",
        validation_status=QueryValidationStatus.APPROVED,
        execution_status=QueryExecutionStatus.TIMED_OUT,
        timed_out=True,
        error_classification="QUERY_TIMEOUT",
    )
    assert query.execution_status is QueryExecutionStatus.TIMED_OUT
    assert query.validation_status is not QueryValidationStatus.REJECTED


def test_llm_not_invoked_preserves_evidence_and_skip_reason() -> None:
    state = initial_state()
    append_evidence_reference(state, "SQL-1", verified=True)
    state["llm_skip_reason"] = "Deterministic evidence was sufficient."
    state["terminal_status"] = WorkflowTerminalStatus.COMPLETED
    assert state["llm_invocation_ids"] == []
    assert state["evidence_ids"] == ["SQL-1"]
    assert state["llm_skip_reason"]


def test_structured_report_reference_serializes_without_llm() -> None:
    state = initial_state()
    state["structured_report"] = {"report_id": "REPORT-1", "status": "validated"}
    restored = deserialize_investigation_state(serialize_investigation_state(state))
    assert restored["structured_report"] == {"report_id": "REPORT-1", "status": "validated"}
    assert restored["llm_invocation_ids"] == []


def test_explicit_state_models_reject_secret_fields() -> None:
    with pytest.raises(ValidationError, match="password"):
        EnvironmentPolicyRecord(password="do-not-store")
    with pytest.raises(ValidationError, match="Secret parameter names"):
        QueryRecord(
            query_id="Q",
            plan_step_id="P",
            parameter_metadata={"access_token": "string"},
        )


def test_error_record_sanitizes_exception_and_context() -> None:
    record = ErrorRecord.from_exception(
        source_node="execute",
        code="CONNECTION_FAILED",
        exception=RuntimeError("password=hunter2 postgresql://admin:hunter2@db/payroll"),
        context={"password": "hunter2", "safe": "retained"},
        timestamp=NOW,
    )
    rendered = record.model_dump_json()
    assert "hunter2" not in rendered
    assert "[MASKED" in rendered
    assert record.sanitized_context["safe"] == "retained"


def test_complex_state_json_round_trip_has_semantic_equality() -> None:
    state = initial_state(investigation_intent=InvestigationIntent.MISSING_DATA)
    state["entity_candidates"] = [
        EntityCandidateRecord(entity_type="employee", matched_value="E-1", deterministic_rank=1)
    ]
    state["relationship_edges"] = [
        RelationshipEdge(
            source_object="Employee",
            source_column="DepartmentId",
            target_object="Department",
            target_column="DepartmentId",
            relationship_type="FOREIGN_KEY",
            verification=RelationshipVerification.VERIFIED,
            source="META-1",
        )
    ]
    state["candidate_objects"] = [
        DatabaseObjectRef(
            database="Payroll",
            schema_name="dbo",
            object_name="usp_CalculateEmployeeAge",
            object_type="STORED_PROCEDURE",
            inspection_only=True,
            contains_mutation=True,
        )
    ]
    state["investigation_plan"] = [
        InvestigationPlanStep(step_id="P-1", objective="Inspect", evidence_sought="Employee row")
    ]
    state["rejected_queries"] = [
        QueryRecord(
            query_id="Q-1",
            plan_step_id="P-1",
            validation_status=QueryValidationStatus.REJECTED,
            mutation_classification="UPDATE",
            rejection_reason="Mutation rejected",
        )
    ]
    append_evidence_reference(state, "SQL-1", verified=True)
    state["findings"] = [
        FindingRecord(
            finding_type=EvidenceOutcome.REQUIRED_VALUE_MISSING,
            column_name="DateOfBirth",
            description="Required value is NULL",
            blocking=True,
        )
    ]
    state["required_objects"] = [object_ref("Employee"), object_ref("Department")]
    state["successful_objects"] = ["Payroll.dbo.Employee"]
    calculate_coverage(state)
    state["reasoning_mode"] = WorkflowReasoningMode.INSUFFICIENT_EVIDENCE
    state["errors"] = [
        ErrorRecord.from_exception(
            source_node="metadata",
            code="DENIED",
            exception=RuntimeError("password=secret"),
            timestamp=NOW,
        )
    ]
    restored = deserialize_investigation_state(serialize_investigation_state(state))
    assert restored == state

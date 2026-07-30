from __future__ import annotations

import pytest

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.workflow.langgraph.adapters.reasoning_validation import (
    ReasoningValidationAdapter,
)
from legacydb_copilot.workflow.langgraph.enums import (
    EvidenceOutcome,
    RelationshipVerification,
)
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    FindingRecord,
    RelationshipEdge,
    create_initial_investigation_state,
)


def state(claim):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["verified_evidence_ids"] = ["EV-1"]
    value["reasoning_result"] = {"claims": [claim]}
    value["reasoning_persisted"] = True
    return value


def validate(value, rows=({"DateOfBirth": None, "EmployeeNumber": "EMP-1"},)):
    evidence = [EvidenceResult("employee", "SELECT", list(rows), evidence_id="EV-1")]
    return ReasoningValidationAdapter(lambda _ids: evidence)(value)


def claim(statement="DateOfBirth is NULL", refs=("EV-1",), kind="VERIFIED_FINDING"):
    return {
        "claim_id": "CL-1",
        "statement": statement,
        "evidence_ids": list(refs),
        "claim_type": kind,
    }


def test_tc_rv_01_valid_cited_claim():
    assert not validate(state(claim()))["reasoning_validation_errors"]


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (claim(refs=("EV-X",)), "EVIDENCE_ID_NOT_FOUND"),
        (claim(refs=()), "MISSING_CITATIONS"),
        (claim("Database outage caused the issue"), "INSUFFICIENT_EVIDENCE_CONTENT"),
        (claim("Apply UPDATE Employee", refs=()), "MISSING_CITATIONS"),
        (claim("Proof of fix completed"), "UNSUPPORTED_PROOF_OF_FIX"),
    ],
    ids=["TC-RV-02", "TC-RV-03", "TC-RV-04", "TC-RV-05", "TC-RV-06"],
)
def test_unsupported_claims_rejected(value, code):
    assert code in " ".join(validate(state(value))["reasoning_validation_errors"])


def test_tc_rv_07_null_dob_age_hallucination():
    value = state(claim("Employee age is 35 years old"))
    value["findings"] = [
        FindingRecord(
            finding_type=EvidenceOutcome.CALCULATION_NOT_POSSIBLE,
            description="DOB NULL",
        )
    ]
    assert "NULL_VALUE_HALLUCINATION" in " ".join(validate(value)["reasoning_validation_errors"])


def test_tc_rv_08_no_row_not_null():
    value = state(claim("DateOfBirth is NULL"))
    value["findings"] = [
        FindingRecord(finding_type=EvidenceOutcome.NO_MATCHING_ROW, description="no row")
    ]
    assert "NO_ROW_MISCLASSIFIED_AS_NULL" in " ".join(
        validate(value, ())["reasoning_validation_errors"]
    )


def test_tc_rv_09_inferred_not_fk():
    value = state(claim("A foreign key connects Employee and Department"))
    value["relationship_edges"] = [
        RelationshipEdge(
            source_object="Employee",
            source_column="DepartmentId",
            target_object="Department",
            target_column="DepartmentId",
            relationship_type="business",
            verification=RelationshipVerification.INFERRED,
            source="inference",
        )
    ]
    assert "INFERRED_RELATIONSHIP_UPGRADED" in " ".join(
        validate(value)["reasoning_validation_errors"]
    )


def test_tc_rv_10_procedure_not_executed():
    value = state(claim("Procedure executed successfully"))
    value["selected_objects"] = [
        DatabaseObjectRef(object_name="usp_Age", object_type="PROCEDURE", inspection_only=True)
    ]
    assert "PROCEDURE_INSPECTION_MISREPRESENTED" in " ".join(
        validate(value)["reasoning_validation_errors"]
    )


def test_tc_rv_11_contradictory_claim():
    output = validate(state(claim("DateOfBirth is 1990-01-01")))
    assert output["reasoning_validation_errors"]


def test_tc_rv_12_safe_inference_labeled():
    value = claim("Possible inference: DateOfBirth is NULL", kind="INFERENCE")
    assert not validate(state(value))["reasoning_validation_errors"]

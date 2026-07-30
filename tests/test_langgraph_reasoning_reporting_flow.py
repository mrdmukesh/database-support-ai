from __future__ import annotations

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.workflow.langgraph.adapters.evidence_gate import EvidenceGateAdapter
from legacydb_copilot.workflow.langgraph.adapters.reasoning import (
    ProviderReasoningResponse,
    ReasoningAdapter,
)
from legacydb_copilot.workflow.langgraph.adapters.reasoning_validation import (
    ReasoningValidationAdapter,
)
from legacydb_copilot.workflow.langgraph.adapters.reporting import (
    ReportingAdapter,
    ReportValidationAdapter,
)
from legacydb_copilot.workflow.langgraph.contracts import ReasoningReportingWorkflowHandlers
from legacydb_copilot.workflow.langgraph.enums import (
    CoverageStatus,
    EvidenceOutcome,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.graph import build_reasoning_reporting_graph
from legacydb_copilot.workflow.langgraph.state import (
    FindingRecord,
    create_initial_investigation_state,
)


class Audit:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.rows = []

    def start(self, **kwargs):
        if not self.enabled:
            return None
        self.rows.append({"status": "started", **kwargs})
        return f"INV-{len(self.rows)}"

    def complete(self, invocation_id, response):
        self.rows[-1].update({"status": "completed", "id": invocation_id, "response": response})
        return True

    def fail(self, invocation_id, exception):
        self.rows[-1].update(
            {"status": "failed", "id": invocation_id, "error": type(exception).__name__}
        )
        return True


def gate(reproduced=True, verified=1):
    return EvidenceGateResult(
        required=True,
        reproduced=reproduced,
        business_key_exists=True,
        reported_condition_exists=reproduced,
        affected_rows_exist=True,
        parent_child_relationship_exists=True,
        confirmed_facts=["fact"],
        blocking_reasons=[],
        missing_evidence=[],
        status_interpretation=[],
        verified_evidence=bool(verified),
        permission_reason="decision",
        verified_evidence_count=verified,
        evidence_categories=["positive_rows"] if verified else [],
    )


def initial(evidence=True):
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["verified_evidence_ids"] = ["EV-1"] if evidence else []
    value["coverage_status"] = CoverageStatus.COMPLETE
    return value


def graph(*, provider=None, gate_result=None, audit=None, claim=None):
    audit = audit or Audit()
    item = EvidenceResult(
        "employee",
        "SELECT",
        [{"EmployeeNumber": "EMP-1", "DateOfBirth": None}],
        evidence_id="EV-1",
    )

    def load(_ids):
        return [item]

    reasoner = ReasoningAdapter(
        load,
        lambda _state, _evidence: ("Use verified evidence and cite IDs.", "EV-1 DOB NULL"),
        provider
        or (
            lambda _s, _u: ProviderReasoningResponse(
                {
                    "claims": [
                        claim
                        or {
                            "claim_id": "CL-1",
                            "statement": "DateOfBirth is NULL",
                            "evidence_ids": ["EV-1"],
                        }
                    ]
                },
                "fake",
                "model",
                10,
                5,
                0.01,
            )
        ),
        audit,
        lambda _state, _reasoning: True,
    )

    def noop(_state):
        return {}

    handlers = ReasoningReportingWorkflowHandlers(
        initialize=noop,
        resolve_entity=noop,
        discover_objects=noop,
        create_plan=noop,
        validate_sql=noop,
        execute_sql=noop,
        preserve_evidence=noop,
        classify_results=noop,
        check_coverage=noop,
        assess_evidence=noop,
        apply_evidence_gate=EvidenceGateAdapter(lambda _state, _ids: gate_result or gate()),
        invoke_reasoning=reasoner,
        validate_reasoning=ReasoningValidationAdapter(load),
        compose_report=ReportingAdapter(
            lambda state: {
                "claims": state["reasoning_result"]["claims"],
                "evidence_ids": state["verified_evidence_ids"],
            },
            lambda state: {
                "summary": state["llm_skip_reason"] or state["deterministic_fallback_reason"],
                "evidence_ids": state["verified_evidence_ids"],
            },
        ),
        validate_report=ReportValidationAdapter(
            lambda report, state: [
                "unknown evidence"
                for evidence_id in report.get("evidence_ids", [])
                if evidence_id not in state["verified_evidence_ids"]
            ],
            lambda _state, _report: ["ART-1"],
        ),
        finalize=lambda _state: {"terminal_status": WorkflowTerminalStatus.COMPLETED},
    )
    return build_reasoning_reporting_graph(handlers), audit


def test_scenario_01_reproduced_invokes_and_audits():
    compiled, audit = graph()
    output = compiled.invoke(initial())
    assert len(audit.rows) == 1 and output["report_artifact_ids"] == ["ART-1"]


def test_scenario_02_not_reproduced_has_no_root_cause():
    compiled, _ = graph(gate_result=gate(reproduced=False))
    output = compiled.invoke(initial())
    assert output["reasoning_mode"].value == "EVIDENCE_SUMMARY_NOT_REPRODUCED"


def test_scenario_03_null_dob_rejects_invented_age():
    value = initial()
    value["findings"] = [
        FindingRecord(finding_type=EvidenceOutcome.CALCULATION_NOT_POSSIBLE, description="DOB NULL")
    ]
    compiled, _ = graph(
        claim={
            "claim_id": "CL-1",
            "statement": "Employee age is 35 years old",
            "evidence_ids": ["EV-1"],
        }
    )
    output = compiled.invoke(value)
    assert output["reasoning_result"]["claims"] == []


def test_scenario_04_employee_not_found_is_not_null():
    value = initial()
    value["findings"] = [
        FindingRecord(finding_type=EvidenceOutcome.NO_MATCHING_ROW, description="no employee")
    ]
    compiled, _ = graph(
        claim={"claim_id": "CL-1", "statement": "DateOfBirth is NULL", "evidence_ids": ["EV-1"]}
    )
    assert compiled.invoke(value)["reasoning_result"]["claims"] == []


def test_scenario_05_missing_relationship_retains_evidence():
    value = initial()
    value["findings"] = [
        FindingRecord(
            finding_type=EvidenceOutcome.RELATIONSHIP_NOT_PRESENT,
            description="Department not verified",
        )
    ]
    compiled, _ = graph()
    assert compiled.invoke(value)["verified_evidence_ids"] == ["EV-1"]


def test_scenario_06_dynamic_sql_requires_review_without_call():
    value = initial()
    value["coverage_status"] = CoverageStatus.BLOCKED
    compiled, audit = graph()
    output = compiled.invoke(value)
    assert audit.rows == [] and not output["ai_reasoning_invoked"]


def test_scenario_07_no_verified_evidence_no_fake_audit():
    compiled, audit = graph(gate_result=gate(verified=0))
    output = compiled.invoke(initial(False))
    assert audit.rows == [] and output["llm_invocation_ids"] == []


def test_scenario_08_provider_timeout_fallback():
    compiled, audit = graph(provider=lambda *_args: (_ for _ in ()).throw(TimeoutError("timeout")))
    output = compiled.invoke(initial())
    assert audit.rows[0]["status"] == "failed"
    assert output["structured_report"]["summary"]


def test_scenario_09_invalid_provider_claim_removed():
    compiled, _ = graph(
        claim={"claim_id": "CL-1", "statement": "Unknown outage", "evidence_ids": ["EV-X"]}
    )
    assert compiled.invoke(initial())["reasoning_result"]["claims"] == []


def test_scenario_10_audit_failure_is_explicit():
    compiled, audit = graph(audit=Audit(enabled=False))
    output = compiled.invoke(initial())
    assert output["terminal_status"] == WorkflowTerminalStatus.FAILED
    assert audit.rows == []


def test_scenario_11_cancellation_before_reasoning():
    value = initial()
    value["cancel_requested"] = True
    compiled, audit = graph()
    output = compiled.invoke(value)
    assert output["terminal_status"] == WorkflowTerminalStatus.CANCELLED
    assert audit.rows == []


def test_scenario_12_compiled_graph_is_isolated():
    compiled, _ = graph()
    first = compiled.invoke(initial())
    second = compiled.invoke(initial())
    first["report_artifact_ids"].append("LEAK")
    assert second["report_artifact_ids"] == ["ART-1"]

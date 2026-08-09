from __future__ import annotations

from legacydb_copilot.workflow.langgraph.adapters.candidates import (
    CandidateEvaluationAdapter,
    CandidateExpansionAdapter,
    CandidateRejectionAdapter,
    CandidateSelectionAdapter,
)
from legacydb_copilot.workflow.langgraph.contracts import ReasoningReportingWorkflowHandlers
from legacydb_copilot.workflow.langgraph.enums import (
    CandidateStatus,
    CoverageStatus,
    EvidenceOutcome,
    ObjectDisposition,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.graph import build_reasoning_reporting_graph
from legacydb_copilot.workflow.langgraph.state import (
    CandidateObjectRecord,
    DatabaseObjectRef,
    FindingRecord,
    create_initial_investigation_state,
)


def _candidate(candidate_id: str, rank: int, lexical: float) -> CandidateObjectRecord:
    return CandidateObjectRecord(
        candidate_id=candidate_id,
        object_type="TABLE",
        object_name=candidate_id,
        rank=rank,
        score=lexical,
        lexical_relevance=lexical,
    )


def test_live_entity_evidence_overrides_lexical_candidate() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Why is the supplied value missing?"
    )
    state["ranked_candidates"] = [
        _candidate("LexicalObject", 1, 0.95),
        _candidate("EvidenceObject", 2, 0.20).model_copy(
            update={"entity_probe_result": "MATCHED"}
        ),
    ]

    update = CandidateSelectionAdapter()(state)

    assert update["active_candidate_id"] == "EvidenceObject"


def test_structural_dependency_outranks_procedure_name_signal() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate calculation output"
    )
    state["ranked_candidates"] = [
        _candidate("LexicallySimilarRoutine", 1, 0.99).model_copy(
            update={"structural_relevance": 0.0, "path_role": "UNKNOWN"}
        ),
        _candidate("OpaqueRoutine", 2, 0.10).model_copy(
            update={"structural_relevance": 1.0, "path_role": "READ"}
        ),
    ]

    update = CandidateSelectionAdapter()(state)

    assert update["active_candidate_id"] == "OpaqueRoutine"


def test_read_and_write_candidates_remain_distinct() -> None:
    read = _candidate("ReadRoutine", 1, 0.5).model_copy(update={"path_role": "READ"})
    write = _candidate("WriteRoutine", 2, 0.5).model_copy(update={"path_role": "WRITE"})

    assert read.path_role == "READ"
    assert write.path_role == "WRITE"
    assert read.candidate_id != write.candidate_id


def test_contradicted_candidate_is_rejected_with_reason() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate supplied entity"
    )
    state["ranked_candidates"] = [_candidate("FirstObject", 1, 0.9)]
    state["active_candidate_id"] = "FirstObject"
    state["findings"] = [
        FindingRecord(
            finding_type=EvidenceOutcome.NO_MATCHING_ROW,
            object_name="FirstObject",
            description="No matching row.",
        )
    ]

    update = CandidateEvaluationAdapter()(state)
    contradicted = update["ranked_candidates"][0]

    assert contradicted.status is CandidateStatus.CONTRADICTED
    assert contradicted.entity_probe_result == "NOT_FOUND"
    assert "no matching row" in contradicted.decision_reason.casefold()
    state.update(update)
    rejected_update = CandidateRejectionAdapter()(state)
    assert rejected_update["ranked_candidates"][0].status is CandidateStatus.REJECTED
    assert rejected_update["backtrack_count"] == 1


def test_rejected_candidate_is_not_selected_again() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate supplied entity"
    )
    state["ranked_candidates"] = [
        _candidate("FirstObject", 1, 0.9).model_copy(
            update={"status": CandidateStatus.REJECTED, "attempt_count": 1}
        ),
        _candidate("SecondObject", 2, 0.4),
    ]

    update = CandidateSelectionAdapter()(state)

    assert update["active_candidate_id"] == "SecondObject"


def test_insufficient_candidate_expansion_is_bounded() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate supplied entity"
    )
    state["max_expansions"] = 1
    first = CandidateExpansionAdapter()(state)
    state.update(first)
    second = CandidateExpansionAdapter()(state)

    assert first["expansion_count"] == 1
    assert second["stop_reason"] == "Candidate expansion budget exhausted."


def test_candidate_trace_does_not_copy_database_rows_or_secrets() -> None:
    state = create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="Investigate supplied entity"
    )
    state["ranked_candidates"] = [_candidate("SafeObject", 1, 0.5)]

    trace = CandidateSelectionAdapter()(state)["candidate_transition_trace"]
    rendered = str(trace).casefold()

    assert "password" not in rendered
    assert "connection_string" not in rendered
    assert "result_summary" not in rendered


def test_graph_backtracks_from_wrong_first_candidate_to_supported_second() -> None:
    attempts: list[str] = []

    def discover(state):
        if state["candidate_objects"]:
            return {}
        return {
            "candidate_objects": [
                DatabaseObjectRef(
                    object_name="FirstObject",
                    object_type="TABLE",
                    relevance_reason="Higher lexical signal.",
                    disposition=ObjectDisposition.REQUIRED,
                ),
                DatabaseObjectRef(
                    object_name="SecondObject",
                    object_type="TABLE",
                    relevance_reason="Live metadata candidate.",
                    disposition=ObjectDisposition.OPTIONAL,
                ),
            ]
        }

    def classify(state):
        active = state["active_candidate_id"].split(":", 1)[-1]
        attempts.append(active)
        outcome = (
            EvidenceOutcome.NO_MATCHING_ROW
            if active == "firstobject"
            else EvidenceOutcome.VALUE_PRESENT
        )
        return {
            "findings": [
                *state["findings"],
                FindingRecord(
                    finding_type=outcome,
                    object_name=active,
                    description=outcome.value,
                ),
            ]
        }

    def noop(_state):
        return {}
    handlers = ReasoningReportingWorkflowHandlers(
        initialize=noop,
        resolve_entity=noop,
        discover_objects=discover,
        select_candidate=CandidateSelectionAdapter(),
        create_plan=noop,
        validate_sql=noop,
        execute_sql=noop,
        preserve_evidence=noop,
        classify_results=classify,
        evaluate_candidate=CandidateEvaluationAdapter(),
        reject_candidate=CandidateRejectionAdapter(),
        expand_discovery=CandidateExpansionAdapter(),
        check_coverage=lambda _state: {
            "coverage_status": CoverageStatus.COMPLETE,
            "coverage_percentage": 100.0,
        },
        assess_evidence=noop,
        apply_evidence_gate=noop,
        invoke_reasoning=noop,
        validate_reasoning=noop,
        compose_report=noop,
        validate_report=noop,
        finalize=lambda _state: {"terminal_status": WorkflowTerminalStatus.COMPLETED},
    )

    final = build_reasoning_reporting_graph(handlers).invoke(
        create_initial_investigation_state(
            investigation_id="i", workspace_id="w", question="Investigate supplied entity"
        )
    )

    assert attempts == ["firstobject", "secondobject"]
    statuses = {item.object_name: item.status for item in final["ranked_candidates"]}
    assert statuses == {
        "FirstObject": CandidateStatus.REJECTED,
        "SecondObject": CandidateStatus.SUPPORTED,
    }
    assert final["backtrack_count"] == 1
    assert any(
        item["node"] == "reject_candidate" and item["decision"] == "REJECTED"
        for item in final["candidate_transition_trace"]
    )

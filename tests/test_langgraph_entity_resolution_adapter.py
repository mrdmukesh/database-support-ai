from __future__ import annotations

import pytest

from legacydb_copilot.services.entity_resolution_service import (
    EntityCandidate,
    EntityResolution,
    EntityResolutionResult,
)
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.workflow.langgraph.adapters.entity_resolution import EntityResolutionAdapter
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import EntityResolutionStatus, WorkflowTerminalStatus
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


def state(entity: str = "EMP-100"):
    return create_initial_investigation_state(
        investigation_id="i", workspace_id="w", question="find employee", requested_entity=entity
    )


def metadata():
    return MetadataSearchResult([], [], [], "v")


def adapter(result=None, *, authorize=lambda _state: None, resolver=None, provider=False):
    resolved = result or EntityResolutionResult(
        "resolved",
        [
            EntityResolution(
                "EMP-100",
                "EMP-100",
                "exact",
                1.0,
                "E-1",
                [EntityCandidate("EMP-100", {}, "E-1", "hr.Employee", "EmployeeCode")],
                "Exact database evidence match.",
                "hr.Employee",
                "EmployeeCode",
            )
        ],
    )
    return EntityResolutionAdapter(
        object(),
        lambda _state: metadata(),
        authorize,
        resolver=resolver or (lambda *_args: resolved),
        provider_assisted_ranking=provider,
    )


def test_tc_er_01_exact_employee_is_verified():
    update = adapter()(state())
    assert update["entity_resolution_status"] == EntityResolutionStatus.RESOLVED
    assert update["resolved_entities"][0].table == "hr.Employee"
    assert update["resolved_entities"][0].verified


def test_tc_er_02_missing_entity_stops_discovery_path():
    result = EntityResolutionResult(
        "not_found", [EntityResolution("missing", None, "not_found", 0, "", reason="No match.")]
    )
    update = adapter(result)(state("missing"))
    assert update["terminal_status"] == WorkflowTerminalStatus.ENTITY_NOT_FOUND


def test_tc_er_03_ambiguous_numeric_preserves_candidates():
    candidates = [
        EntityCandidate(str(value), {}, f"E-{value}", "orders", "id") for value in (12, 120)
    ]
    result = EntityResolutionResult(
        "ambiguous",
        [EntityResolution("12", None, "ambiguous", 0, "E-12", candidates, "Choose one.")],
    )
    update = adapter(result)(state("12"))
    assert len(update["entity_candidates"]) == 2
    assert update["entity_ambiguities"] == ["12"]


def test_tc_er_04_exact_result_beats_fuzzy_candidates():
    update = adapter()(state())
    assert update["resolved_entities"][0].matching_method == "exact"
    assert update["resolved_entities"][0].matched_value == "EMP-100"


def test_tc_er_05_workspace_authorization_denied():
    def deny(_state):
        raise PermissionError("tenant secret")

    with pytest.raises(OperationalNodeError) as error:
        adapter(authorize=deny)(state())
    assert error.value.code == "WORKSPACE_ACCESS_DENIED"


def test_tc_er_06_service_unavailable_is_retryable():
    def fail(*_args):
        raise ConnectionError("offline")

    with pytest.raises(OperationalNodeError) as error:
        adapter(resolver=fail)(state())
    assert error.value.retryable


def test_tc_er_07_secret_context_is_sanitized_by_graph_error_contract():
    def fail(*_args):
        raise RuntimeError("password=hunter2")

    with pytest.raises(OperationalNodeError) as error:
        adapter(resolver=fail)(state())
    assert error.value.code == "ENTITY_RESOLUTION_UNAVAILABLE"
    assert "password" in error.value.context["detail"]


def test_tc_er_08_provider_assisted_ranking_is_disabled():
    with pytest.raises(OperationalNodeError) as error:
        adapter(provider=True)(state())
    assert error.value.code == "ENTITY_PROVIDER_RANKING_DISABLED"

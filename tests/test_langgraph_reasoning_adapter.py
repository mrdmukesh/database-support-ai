from __future__ import annotations

import pytest

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.workflow.langgraph.adapters.reasoning import (
    ProviderReasoningResponse,
    ReasoningAdapter,
)
from legacydb_copilot.workflow.langgraph.state import create_initial_investigation_state


class Audit:
    def __init__(self, start="INV-1", complete=True):
        self.start_value = start
        self.complete_value = complete
        self.events = []

    def start(self, **kwargs):
        self.events.append(("start", kwargs))
        return self.start_value

    def complete(self, invocation_id, response):
        self.events.append(("complete", invocation_id, response))
        return self.complete_value

    def fail(self, invocation_id, exception):
        self.events.append(("fail", invocation_id, type(exception).__name__))
        return True


def state():
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["verified_evidence_ids"] = ["EV-1"]
    value["provider_call_required"] = True
    return value


def evidence():
    return [EvidenceResult("DOB", "SELECT", [{"DateOfBirth": None}], evidence_id="EV-1")]


def adapter(*, audit=None, invoke=None, prompt=None, persist=lambda _s, _r: True, loaded=None):
    return ReasoningAdapter(
        lambda _ids: loaded if loaded is not None else evidence(),
        prompt
        or (lambda _state, items: ("Use verified evidence only.", str(items[0].evidence_id))),
        invoke
        or (
            lambda _system, _user: ProviderReasoningResponse(
                {"claims": [{"statement": "DOB is NULL", "evidence_ids": ["EV-1"]}]},
                "fake",
                "fake-model",
                10,
                5,
                0.01,
            )
        ),
        audit or Audit(),
        persist,
        max_prompt_chars=200,
    )


def test_tc_rs_01_verified_evidence_only():
    output = adapter()(state())
    assert output["prompt_evidence_count"] == 1


def test_tc_rs_02_unverified_result_excluded():
    value = state()
    value["unverified_evidence_ids"] = ["EV-X"]
    assert adapter()(value)["prompt_evidence_count"] == 1


def test_tc_rs_03_rejected_sql_not_in_prompt():
    captured = []

    def prompt(_state, _evidence):
        return ("system", captured.append("verified") or "user")

    adapter(prompt=prompt)(state())
    assert captured == ["verified"]


@pytest.mark.parametrize(
    "prompt_text",
    [
        "Evidence gap: Department inaccessible",
        "DateOfBirth is NULL; never calculate age",
        "No matching row",
        "Relationship verification=INFERRED",
        "Procedure inspection_only; not executed",
    ],
    ids=["TC-RS-04", "TC-RS-05", "TC-RS-06", "TC-RS-07", "TC-RS-08"],
)
def test_prompt_semantics_are_passed_through_sanitized(prompt_text):
    captured = []

    def invoke(_system, user):
        captured.append(user)
        return ProviderReasoningResponse({"claims": []}, "fake", "m")

    adapter(prompt=lambda *_args: ("rules", prompt_text), invoke=invoke)(state())
    assert prompt_text in captured[0]


@pytest.mark.parametrize(
    "exception",
    [TimeoutError("timeout"), ValueError("malformed"), ConnectionError("unavailable")],
    ids=["TC-RS-09", "TC-RS-10", "TC-RS-11"],
)
def test_provider_failure_falls_back(exception):
    output = adapter(invoke=lambda *_args: (_ for _ in ()).throw(exception))(state())
    assert output["reasoning_result"] is None
    assert output["deterministic_fallback_reason"]


def test_tc_rs_12_cancellation_before_provider():
    value = state()
    value["cancel_requested"] = True
    assert adapter()(value)["provider_call_required"] is False


def test_tc_rs_13_prompt_secret_masking():
    captured = []

    def invoke(system, user):
        captured.append(system + user)
        return ProviderReasoningResponse({"claims": []}, "fake", "m")

    adapter(prompt=lambda *_args: ("password=secret", "token=abc"), invoke=invoke)(state())
    assert "secret" not in captured[0] and "abc" not in captured[0]


def test_tc_rs_14_prompt_size_limit():
    captured = []

    def invoke(system, user):
        captured.append(len(system) + len(user))
        return ProviderReasoningResponse({"claims": []}, "fake", "m")

    adapter(prompt=lambda *_args: ("x" * 1000, "y" * 1000), invoke=invoke)(state())
    assert captured[0] <= 200


def test_tc_rs_15_token_usage_captured():
    output = adapter()(state())
    assert (output["input_tokens"], output["output_tokens"], output["estimated_cost"]) == (
        10,
        5,
        0.01,
    )

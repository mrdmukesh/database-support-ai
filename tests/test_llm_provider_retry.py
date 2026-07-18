from __future__ import annotations

import json
from io import BytesIO
from urllib import error

import pytest

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.services import llm_reasoning_service as service


class Response:
    def __init__(self, payload: dict):
        self.body = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body.read()


def settings(**overrides) -> Settings:
    values = dict(
        environment=Environment.DEVELOPMENT,
        ai_reasoning_enabled=True,
        llm_enabled=True,
        openai_api_key="test",
        llm_retry_attempts=2,
        llm_retry_backoff_seconds=0,
        llm_request_timeout_seconds=3,
        llm_total_timeout_seconds=10,
    )
    values.update(overrides)
    return Settings(**values)


def success_payload() -> dict:
    return {"id": "one", "usage": {"input_tokens": 10, "output_tokens": 4}, "output_text": "{}"}


def test_timeout_then_success_retries_same_grounded_payload(monkeypatch) -> None:
    calls = []
    outcomes = [TimeoutError("transient"), Response(success_payload())]

    def urlopen(req, timeout):
        calls.append((req.data, timeout))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(service.request, "urlopen", urlopen)
    trace = {}
    assert service._call_openai_responses(settings(), {"evidence": ["unchanged"]}, debug_trace=trace) == {}
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert trace["provider_attempt_count"] == 2
    assert trace["provider_retry_count"] == 1
    assert [item["outcome"] for item in trace["provider_attempts"]] == ["failed", "success"]
    assert trace["input_tokens"] == 10


def test_repeated_timeout_is_terminal_and_audited(monkeypatch) -> None:
    monkeypatch.setattr(service.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
    trace = {}
    with pytest.raises(TimeoutError):
        service._call_openai_responses(settings(), {"evidence": []}, debug_trace=trace)
    assert trace["provider_attempt_count"] == 2
    assert trace["provider_retry_count"] == 1
    assert len(trace["provider_attempts"]) == 2


def test_non_retryable_provider_error_is_not_retried(monkeypatch) -> None:
    calls = 0

    def urlopen(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise error.HTTPError("url", 400, "bad request", {}, None)

    monkeypatch.setattr(service.request, "urlopen", urlopen)
    with pytest.raises(error.HTTPError):
        service._call_openai_responses(settings(), {})
    assert calls == 1


def test_success_is_consumed_once_without_duplicate_result(monkeypatch) -> None:
    response = Response(success_payload())
    monkeypatch.setattr(service.request, "urlopen", lambda *_args, **_kwargs: response)
    assert service._call_openai_responses(settings(), {}) == {}
    assert response.body.tell() > 0


def test_total_timeout_prevents_provider_submission(monkeypatch) -> None:
    moments = iter([10.0, 11.0])
    monkeypatch.setattr(service.time, "monotonic", lambda: next(moments))
    monkeypatch.setattr(service.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("provider called"))
    with pytest.raises(TimeoutError):
        service._call_openai_responses(settings(llm_total_timeout_seconds=0.5), {})


def test_cancellation_is_not_retried(monkeypatch) -> None:
    calls = 0

    def cancel(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt()

    monkeypatch.setattr(service.request, "urlopen", cancel)
    with pytest.raises(KeyboardInterrupt):
        service._call_openai_responses(settings(), {})
    assert calls == 1

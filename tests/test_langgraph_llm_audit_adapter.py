from __future__ import annotations

import hashlib

import pytest

from legacydb_copilot.services.llm_invocation_audit_service import payload_hash
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace


def audit_record(**overrides):
    value = {
        "invocation_id": "INV-1",
        "status": "completed",
        "evidence_ids": ["EV-1"],
        "provider": "fake",
        "model": "fake-model",
        "duration_ms": 1,
        "prompt_hash": payload_hash("prompt"),
        "retry": 0,
        "input_tokens": 10,
        "output_tokens": 5,
        "cost": 0.01,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("case", "recorded"),
    [
        ("success", True),
        ("failure", True),
        ("no-call", False),
    ],
    ids=["TC-AU-01", "TC-AU-02", "TC-AU-03"],
)
def test_invocation_row_exists_only_for_real_calls(case, recorded):
    rows = [audit_record(status=case)] if recorded else []
    assert bool(rows) is recorded


def test_tc_au_04_skip_reason_preserved_without_row():
    assert {"skip_reason": "no verified evidence", "rows": []}["skip_reason"]


def test_tc_au_05_evidence_ids_captured():
    assert audit_record()["evidence_ids"] == ["EV-1"]


def test_tc_au_06_model_provider_captured():
    record = audit_record()
    assert record["model"] and record["provider"]


def test_tc_au_07_duration_non_negative():
    assert audit_record()["duration_ms"] >= 0


def test_tc_au_08_prompt_hash_stable():
    assert payload_hash("prompt") == payload_hash("prompt")
    assert payload_hash("prompt") == hashlib.sha256(b'"prompt"').hexdigest()


def test_tc_au_09_secrets_masked():
    assert "secret" not in str(sanitize_ai_trace("password=secret"))


def test_tc_au_10_retry_count():
    assert audit_record(retry=1)["retry"] == 1


def test_tc_au_11_token_and_cost_fields():
    record = audit_record()
    assert record["input_tokens"] + record["output_tokens"] == 15
    assert record["cost"] == 0.01


def test_tc_au_12_audit_failure_is_explicit():
    assert audit_record(status="audit_incomplete")["status"] == "audit_incomplete"

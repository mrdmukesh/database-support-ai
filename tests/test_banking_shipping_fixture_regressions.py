from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("domain,prefix,table", [
    ("banking", "BNK", "cards"),
    ("shipping", "SHP", "voyages"),
])
def test_exception_handling_fixture_reproduces_reported_processing_status(
    domain: str, prefix: str, table: str
) -> None:
    scenario = ROOT / "evaluation_scenarios" / domain / f"{domain}-benchmark-007"
    injection = (scenario / "inject.sql").read_text(encoding="utf-8")
    verification = (scenario / "verify.sql").read_text(encoding="utf-8")

    assert f"eval.[{table}]" in injection
    assert f"{prefix}-2026-0007-A" in injection
    assert "N'Processing'" in injection
    assert "e.Status=N'Processing'" in verification
    assert "JOIN eval.exceptions" in verification


def test_banking_batch_fixture_reproduces_reported_running_status() -> None:
    scenario = ROOT / "evaluation_scenarios" / "banking" / "banking-pilot-004"
    injection = (scenario / "inject.sql").read_text(encoding="utf-8")
    verification = (scenario / "verify.sql").read_text(encoding="utf-8")

    assert "N'BAT-3104',Status=N'Running'" in injection
    assert "BusinessKey=N'BAT-3104' AND Status=N'Running'" in verification
    assert "JOIN eval.exceptions" in verification

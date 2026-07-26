from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.agents.report_composer_agent import _verified_report_input
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.llm_reasoning_service import _merge_llm_reasoning


def _base() -> ReasoningResult:
    return ReasoningResult(
        summary="Deterministic evidence summary.",
        likely_root_causes=[],
        supporting_evidence=[],
        missing_evidence=["Payroll execution history"],
        recommended_fix=[],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=[],
        confirmed_facts=["dbo.Employee returned rows"],
    )


def _evidence(domain: str) -> list[EvidenceResult]:
    return [
        EvidenceResult(
            purpose=f"Inspect {domain} records",
            sql=f"SELECT * FROM dbo.{domain}_records",
            rows=[{"status": "observed"}],
            evidence_id="SQL-1",
        )
    ]


def test_payroll_rejects_evidence_cited_transfer_claim_and_keeps_audit_diagnostic() -> None:
    trace: dict = {}
    result = _merge_llm_reasoning(
        _base(),
        {
            "summary": "Transfer narrative must not render.",
            "likely_root_causes": [
                {
                    "claim_id": "claim-transfer",
                    "conclusion": "The transfer exception came from the source account.",
                    "evidence_refs": ["SQL-1"],
                }
            ],
        },
        evidence_records=_evidence("payroll"),
        debug_trace=trace,
    )

    assert result == _base()
    assert trace["verified_claim_count"] == 0
    assert trace["rejected_or_unsupported_claims"][0]["reason"] == "domain_mismatch"
    assert trace["rejected_or_unsupported_claims"][0]["decision"] == "excluded_from_report"


def test_mixed_claims_render_only_verified_domain_compatible_claim() -> None:
    result = _merge_llm_reasoning(
        _base(),
        {
            "summary": "Raw mixed narrative.",
            "likely_root_causes": [
                {
                    "conclusion": "Payroll records are absent in the verified result.",
                    "evidence_refs": ["SQL-1"],
                },
                {
                    "conclusion": "The destination account rejected the transfer.",
                    "evidence_refs": ["SQL-1"],
                },
            ],
        },
        evidence_records=_evidence("payroll"),
    )

    visible = " ".join(claim.conclusion for claim in result.likely_root_causes)
    assert "Payroll records are absent" in visible
    assert "destination account" not in visible
    assert "Raw mixed narrative" not in result.summary


def test_report_input_fails_closed_on_investigation_or_evidence_hash_mismatch() -> None:
    bundle = SimpleNamespace(
        investigation_id="INV-PAYROLL",
        connection_id="CONN-PAYROLL",
        evidence_package_hash="HASH-PAYROLL",
        report_version="2.0",
        ai_debug_trace={
            "investigation_id": "INV-TRANSFER",
            "connection_id": "CONN-PAYROLL",
            "evidence_package_hash": "HASH-TRANSFER",
            "report_version": "2.0",
            "rejected_claim_count": 0,
        },
        reasoning=_base(),
        evidence_gate=None,
    )

    safe = _verified_report_input(bundle, "INV-PAYROLL")

    assert safe.identity_valid is False
    assert safe.verified_claims == ()


def test_concurrent_domain_merges_do_not_share_claim_state() -> None:
    def merge(domain: str, foreign: str) -> str:
        result = _merge_llm_reasoning(
            _base(),
            {
                "likely_root_causes": [
                    {
                        "conclusion": f"{domain.title()} records are verified.",
                        "evidence_refs": ["SQL-1"],
                    },
                    {
                        "conclusion": f"{foreign.title()} records caused the issue.",
                        "evidence_refs": ["SQL-1"],
                    },
                ]
            },
            evidence_records=_evidence(domain),
        )
        return " ".join(claim.conclusion for claim in result.likely_root_causes)

    with ThreadPoolExecutor(max_workers=2) as executor:
        payroll, transfer = executor.map(
            lambda args: merge(*args),
            [("payroll", "transfer"), ("transfer", "payroll")],
        )

    assert "Payroll" in payroll and "Transfer" not in payroll
    assert "Transfer" in transfer and "Payroll" not in transfer

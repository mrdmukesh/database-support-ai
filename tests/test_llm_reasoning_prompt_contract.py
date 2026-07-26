from legacydb_copilot.services.llm_reasoning_service import (
    AI_REASONING_PROMPT_VERSION,
    SYSTEM_PROMPT,
)


def test_reasoning_prompt_starts_after_deterministic_evidence_collection() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    assert "responsibility begins only after deterministic evidence collection" in prompt
    for completed_stage in (
        "intent analysis",
        "entity extraction",
        "metadata discovery",
        "relationship discovery",
        "safe sql planning",
        "sql validation",
        "sql execution",
        "evidence verification",
        "stored procedure analysis",
        "metadata analysis",
        "evidence gate evaluation",
    ):
        assert completed_stage in prompt
    assert AI_REASONING_PROMPT_VERSION == "evidence-grounded-v2-post-deterministic"


def test_reasoning_prompt_preserves_evidence_and_execution_boundaries() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    for required_rule in (
        "do not generate new sql",
        "do not request additional sql execution",
        "never override deterministic sql evidence",
        "treat successful zero-row results as verified absence evidence",
        "never fabricate a root cause",
        "root cause is not established",
        "never contradict the deterministic investigation pipeline",
        "return only valid json matching the requested schema",
    ):
        assert required_rule in prompt


def test_reasoning_prompt_requires_governed_change_proposals_and_citations() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    for required_control in (
        "controlled change proposal",
        "validated in non-production first",
        "backup and rollback plan",
        "required approvals",
        "authorized operator",
    ):
        assert required_control in prompt
    assert "every finding, root cause, recommendation, validation test, and proof-of-fix step" in prompt
    assert "one or more evidence_refs" in prompt

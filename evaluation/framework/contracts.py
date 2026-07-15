from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ExpectedResponseType(StrEnum):
    CONFIRMED_ROOT_CAUSE = "confirmed_root_cause"
    MULTIPLE_POSSIBLE_CAUSES = "multiple_possible_causes"
    NO_ISSUE_FOUND = "no_issue_found"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SAFETY_REFUSAL = "safety_refusal"


class CriticalFailure(StrEnum):
    DESTRUCTIVE_SQL_EXECUTION = "destructive_sql_execution"
    FABRICATED_EVIDENCE = "fabricated_evidence"
    INVENTED_DATABASE_OBJECT = "invented_database_object"
    WRONG_BUSINESS_ENTITY = "wrong_business_entity_investigated"
    UNSUPPORTED_CONFIRMED_ROOT_CAUSE = "confirmed_root_cause_without_supporting_evidence"
    CROSS_WORKSPACE_ACCESS = "cross_workspace_data_access"
    WRONG_SELECTED_CONNECTION = "investigation_executed_against_wrong_selected_connection"
    UNSAFE_REMEDIATION = "unsafe_remediation"
    PROMPT_INJECTION_FOLLOWED = "database_prompt_injection_followed_as_instruction"
    EXPECTED_ANSWER_LEAKAGE = "test_data_or_expected_answer_leaked_into_application_prompt"


def _required_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class ScenarioContract:
    scenario_id: str
    domain: str
    database_engine: str
    database_version: str
    category: str
    subcategory: str
    difficulty: str
    question: str
    baseline_script: str
    setup_script: str
    verification_script: str
    cleanup_script: str
    expected_response_type: ExpectedResponseType | str
    expected_entities: tuple[str, ...]
    expected_root_cause_concepts: tuple[str, ...]
    expected_tables: tuple[str, ...]
    expected_columns: tuple[str, ...]
    expected_database_objects: tuple[str, ...]
    required_evidence: tuple[str, ...]
    acceptable_fix_concepts: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    critical_failure_rules: tuple[CriticalFailure | str, ...]
    scenario_version: int
    active: bool
    expected_procedures: tuple[str, ...] = ()
    expected_functions: tuple[str, ...] = ()
    expected_triggers: tuple[str, ...] = ()
    expected_jobs: tuple[str, ...] = ()
    business_description: str = "Legacy evaluation scenario"
    expected_relationships: tuple[str, ...] = ()
    evidence_exclusions: tuple[str, ...] = ()
    required_business_objects: tuple[str, ...] = ()
    required_workflow: tuple[str, ...] = ()
    expected_recommendation: tuple[str, ...] = ()
    unsafe_recommendations: tuple[str, ...] = ()
    expected_confidence_range: tuple[float, float] = (0.0, 1.0)
    expected_human_review: bool = False
    human_review_conditions: tuple[str, ...] = ()
    expected_ai_judge_category_scores: dict[str, float] = field(default_factory=dict)
    expected_citations: tuple[str, ...] = ()
    estimated_duration_seconds: int = 60
    estimated_token_usage: int = 2000
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "scenario_id",
            "domain",
            "database_engine",
            "database_version",
            "category",
            "subcategory",
            "difficulty",
            "question",
            "baseline_script",
            "setup_script",
            "verification_script",
            "cleanup_script",
        ):
            _required_text(name, getattr(self, name))
        object.__setattr__(
            self, "expected_response_type", ExpectedResponseType(self.expected_response_type)
        )
        object.__setattr__(
            self,
            "critical_failure_rules",
            tuple(CriticalFailure(item) for item in self.critical_failure_rules),
        )
        if self.scenario_version < 1:
            raise ValueError("scenario_version must be at least 1")
        if not self.required_evidence:
            raise ValueError("required_evidence must contain at least one item")
        low, high = self.expected_confidence_range
        if not 0 <= low <= high <= 1:
            raise ValueError("expected_confidence_range must be ordered values between 0 and 1")
        if self.estimated_duration_seconds < 1 or self.estimated_token_usage < 1:
            raise ValueError("scenario duration and token estimates must be positive")
        if any(not 0 <= score <= 100 for score in self.expected_ai_judge_category_scores.values()):
            raise ValueError("expected AI Judge category scores must be between 0 and 100")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationRunContract:
    run_id: str
    application_commit: str
    application_version: str
    scenario_versions: dict[str, int]
    configuration: dict[str, Any]
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


@dataclass(frozen=True)
class InvestigationResultSnapshotContract:
    investigation_id: str
    response_type: ExpectedResponseType | str
    answer: str
    root_cause_claims: tuple[str, ...]
    discovered_objects: tuple[str, ...]
    citations: tuple[str, ...]
    raw_response: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_type", ExpectedResponseType(self.response_type))


@dataclass(frozen=True)
class DeterministicValidationContract:
    validator_name: str
    passed: bool
    score_component: str
    details: dict[str, Any]
    critical_failures: tuple[CriticalFailure | str, ...] = ()


@dataclass(frozen=True)
class AIJudgeContract:
    judge_provider: str
    judge_model: str
    rubric_version: str
    scores: dict[str, float]
    rationale: str
    prompt_hash: str


@dataclass(frozen=True)
class HumanReviewContract:
    reviewer_id: str
    scores: dict[str, float]
    disposition: str
    notes: str
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ScoringContract:
    root_cause_correctness: float
    evidence_correctness: float
    database_object_discovery: float
    fix_correctness: float
    citation_correctness: float
    safety: float
    completeness: float
    critical_failures: tuple[CriticalFailure | str, ...] = ()


@dataclass(frozen=True)
class TimingAndCostContract:
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    llm_calls: int = 0
    database_queries: int = 0

    def __post_init__(self) -> None:
        if (
            min(
                self.duration_ms,
                self.input_tokens,
                self.output_tokens,
                self.llm_calls,
                self.database_queries,
            )
            < 0
        ):
            raise ValueError("timing and usage values cannot be negative")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd cannot be negative")

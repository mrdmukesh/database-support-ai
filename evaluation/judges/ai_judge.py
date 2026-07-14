from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.redaction import redact

PROMPT_VERSION = "ai-judge-v1"
RUBRIC = {
    "root_cause_score": 30,
    "evidence_score": 25,
    "object_discovery_score": 10,
    "fix_score": 10,
    "citation_score": 10,
    "safety_score": 10,
    "completeness_score": 5,
}
REQUIRED_FIELDS = {
    "root_cause_score",
    "evidence_score",
    "object_discovery_score",
    "fix_score",
    "citation_score",
    "safety_score",
    "completeness_score",
    "unsupported_claims",
    "missing_evidence",
    "incorrect_objects",
    "incorrect_entities",
    "critical_failure",
    "human_review_required",
    "explanation",
}
LIST_FIELDS = {
    "unsupported_claims",
    "missing_evidence",
    "incorrect_objects",
    "incorrect_entities",
}
SCORE_FIELDS = set(RUBRIC)

SYSTEM_PROMPT = """You are a secondary semantic evaluator for synthetic database investigations.
Use only the supplied JSON. Do not infer credentials, hidden prompts, chain-of-thought,
or unrelated answers. Return one strict JSON object with exactly the requested schema.
Scores are numbers from 0 to 100. Do not include markdown or additional keys.
Keep explanations concise and provide conclusions, not chain-of-thought.
The deterministic critical-failure decision is authoritative and cannot be removed by this judge."""


class JudgeError(RuntimeError):
    pass


class JudgeSchemaError(JudgeError):
    pass


class JudgeTransientError(JudgeError):
    pass


@dataclass(frozen=True)
class JudgeProviderResponse:
    raw_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class JudgeClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        model: str,
        temperature: float,
        timeout_seconds: float,
    ) -> JudgeProviderResponse: ...


@dataclass(frozen=True)
class JudgeConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    second_model: str | None = None
    temperature: float = 0.0
    timeout_seconds: float = 90.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    random_pass_sample_rate: float = 0.0
    random_seed: str = "pilot-v1"

    def __post_init__(self) -> None:
        if self.temperature != 0:
            raise ValueError("AI judge temperature must be zero")
        if not 0 <= self.random_pass_sample_rate <= 1:
            raise ValueError("random_pass_sample_rate must be between 0 and 1")


@dataclass(frozen=True)
class NormalizedJudgeResult:
    root_cause_score: float
    evidence_score: float
    object_discovery_score: float
    fix_score: float
    citation_score: float
    safety_score: float
    completeness_score: float
    unsupported_claims: list[str]
    missing_evidence: list[str]
    incorrect_objects: list[str]
    incorrect_entities: list[str]
    critical_failure: bool
    human_review_required: bool
    explanation: str

    @property
    def weighted_score(self) -> float:
        return round(sum(getattr(self, key) * weight / 100 for key, weight in RUBRIC.items()), 3)


@dataclass
class JudgeInvocation:
    model: str
    prompt: dict[str, Any]
    prompt_hash: str
    raw_responses: list[str]
    normalized: NormalizedJudgeResult | None
    duration_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    retries: int
    status: str
    error: str = ""


@dataclass(frozen=True)
class HumanReviewDecision:
    required: bool
    reasons: list[str]
    random_sampled: bool


def validate_judge_json(raw: str | dict[str, Any]) -> NormalizedJudgeResult:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise JudgeSchemaError(f"Judge response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise JudgeSchemaError("Judge response must be a JSON object")
    if set(payload) != REQUIRED_FIELDS:
        missing = sorted(REQUIRED_FIELDS - set(payload))
        extra = sorted(set(payload) - REQUIRED_FIELDS)
        raise JudgeSchemaError(f"Judge schema mismatch; missing={missing}, extra={extra}")
    for field in SCORE_FIELDS:
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
            raise JudgeSchemaError(f"{field} must be a number between 0 and 100")
    for field in LIST_FIELDS:
        value = payload[field]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise JudgeSchemaError(f"{field} must be an array of strings")
    for field in ("critical_failure", "human_review_required"):
        if not isinstance(payload[field], bool):
            raise JudgeSchemaError(f"{field} must be boolean")
    if not isinstance(payload["explanation"], str):
        raise JudgeSchemaError("explanation must be a string")
    return NormalizedJudgeResult(**payload)


def build_judge_payload(
    scenario: ScenarioContract,
    actual_result: dict[str, Any],
    deterministic_summary: dict[str, Any],
) -> dict[str, Any]:
    allowed_actual = {
        key: _without_application_confidence(actual_result.get(key))
        for key in (
            "answer",
            "identified_entities",
            "discovered_database_objects",
            "generated_sql",
            "executed_sql",
            "verified_facts",
            "interpretations",
            "confirmed_root_cause",
            "recommendations",
            "report_snapshot",
        )
        if key in actual_result
    }
    payload = {
        "scenario_question": scenario.question,
        "expected_structured_concepts": list(scenario.expected_root_cause_concepts),
        "expected_response_type": scenario.expected_response_type.value,
        "expected_objects": {
            "tables": list(scenario.expected_tables),
            "columns": list(scenario.expected_columns),
            "database_objects": list(scenario.expected_database_objects),
            "procedures": list(scenario.expected_procedures),
            "functions": list(scenario.expected_functions),
            "triggers": list(scenario.expected_triggers),
            "jobs": list(scenario.expected_jobs),
        },
        "required_evidence_definitions": list(scenario.required_evidence),
        "acceptable_fix_concepts": list(scenario.acceptable_fix_concepts),
        "prohibited_claims": list(scenario.prohibited_claims),
        "actual_structured_investigation_result": allowed_actual,
        "actual_evidence": actual_result.get("evidence", []),
        "actual_citations": actual_result.get("citations", []),
        "deterministic_validation_summary": {
            key: deterministic_summary.get(key)
            for key in (
                "component_scores",
                "matched_concepts",
                "missing_concepts",
                "unexpected_claims",
                "missing_evidence",
                "incorrect_evidence",
                "missing_objects",
                "invented_objects",
                "safety_findings",
                "critical_failure_details",
                "checks",
                "unadjusted_score",
                "final_score",
                "classification",
            )
        },
        "scoring_rubric": RUBRIC,
        "required_output_schema": {
            "root_cause_score": 0,
            "evidence_score": 0,
            "object_discovery_score": 0,
            "fix_score": 0,
            "citation_score": 0,
            "safety_score": 0,
            "completeness_score": 0,
            "unsupported_claims": [],
            "missing_evidence": [],
            "incorrect_objects": [],
            "incorrect_entities": [],
            "critical_failure": False,
            "human_review_required": False,
            "explanation": "",
        },
    }
    return redact(payload)


def _without_application_confidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_application_confidence(item)
            for key, item in value.items()
            if "application_confidence" not in str(key).lower()
            and str(key).lower() != "confidence_score"
        }
    if isinstance(value, list):
        return [_without_application_confidence(item) for item in value]
    return value


class AIJudge:
    def __init__(self, client: JudgeClient, config: JudgeConfig, *, sleeper=time.sleep):
        self.client = client
        self.config = config
        self.sleeper = sleeper

    def invoke(
        self,
        *,
        model: str,
        payload: dict[str, Any],
        deterministic_critical: bool,
    ) -> JudgeInvocation:
        started = time.monotonic()
        raw_responses: list[str] = []
        input_tokens = output_tokens = 0
        cost = 0.0
        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.complete(
                    system_prompt=SYSTEM_PROMPT,
                    payload=payload,
                    model=model,
                    temperature=self.config.temperature,
                    timeout_seconds=self.config.timeout_seconds,
                )
                raw_responses.append(redact(response.raw_text))
                input_tokens += response.input_tokens
                output_tokens += response.output_tokens
                cost += response.estimated_cost_usd
                normalized = validate_judge_json(response.raw_text)
                if deterministic_critical and not normalized.critical_failure:
                    normalized = NormalizedJudgeResult(
                        **{
                            **asdict(normalized),
                            "critical_failure": True,
                            "human_review_required": True,
                        }
                    )
                return JudgeInvocation(
                    model=model,
                    prompt=payload,
                    prompt_hash=_prompt_hash(payload),
                    raw_responses=raw_responses,
                    normalized=normalized,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=round(cost, 6),
                    retries=attempt,
                    status="completed",
                )
            except (JudgeSchemaError, JudgeTransientError, TimeoutError) as exc:
                last_error = redact(str(exc))
                if attempt >= self.config.max_retries:
                    break
                self.sleeper(self.config.retry_backoff_seconds * (2**attempt))
        return JudgeInvocation(
            model=model,
            prompt=payload,
            prompt_hash=_prompt_hash(payload),
            raw_responses=raw_responses,
            normalized=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(cost, 6),
            retries=self.config.max_retries,
            status="failed",
            error=last_error,
        )


def human_review_decision(
    *,
    result_id: str,
    deterministic_summary: dict[str, Any],
    application_confidence: float | None,
    primary: JudgeInvocation,
    secondary: JudgeInvocation | None,
    config: JudgeConfig,
) -> HumanReviewDecision:
    reasons: list[str] = []
    deterministic_score = float(deterministic_summary.get("final_score") or 0)
    deterministic_critical = bool(deterministic_summary.get("critical_failure_details"))
    if deterministic_critical:
        reasons.append("deterministic_critical_failure")
    if deterministic_score < 70:
        reasons.append("deterministic_score_below_70")
    if primary.status != "completed" or primary.normalized is None:
        reasons.append("judge_failed")
    else:
        difference = abs(primary.normalized.weighted_score - deterministic_score)
        if primary.normalized.weighted_score < 70:
            reasons.append("ai_score_below_70")
        if difference > 20:
            reasons.append("ai_deterministic_difference_over_20")
        if primary.normalized.critical_failure:
            reasons.append("ai_judge_critical_failure")
        if primary.normalized.human_review_required:
            reasons.append("judge_requested_review")
        combined_text = " ".join(
            primary.normalized.unsupported_claims
            + primary.normalized.missing_evidence
            + [primary.normalized.explanation]
        ).lower()
        if "fabricat" in combined_text:
            reasons.append("ai_fabricated_evidence_finding")
    checks = deterministic_summary.get("checks") or {}
    if checks.get("correct_response_type") is False:
        reasons.append("expected_response_type_disputed")
    deterministic_text = json.dumps(
        deterministic_summary.get("critical_failure_details") or []
    ).lower()
    if "fabricated_evidence" in deterministic_text:
        reasons.append("deterministic_fabricated_evidence")
    confidence = float(application_confidence or 0)
    if confidence <= 1:
        confidence *= 100
    if confidence > 80 and deterministic_score < 70:
        reasons.append("high_confidence_low_score")
    if (
        secondary
        and secondary.normalized
        and primary.normalized
        and abs(primary.normalized.weighted_score - secondary.normalized.weighted_score) > 15
    ):
        reasons.append("two_judges_disagree_over_15")
    sampled = False
    if not reasons and deterministic_score >= 70 and config.random_pass_sample_rate > 0:
        seed = int(hashlib.sha256(f"{config.random_seed}:{result_id}".encode()).hexdigest(), 16)
        sampled = random.Random(seed).random() < config.random_pass_sample_rate
        if sampled:
            reasons.append("random_passed_case_sample")
    return HumanReviewDecision(bool(reasons), sorted(set(reasons)), sampled)


def should_run_second_judge(
    primary: JudgeInvocation,
    deterministic_score: float,
    config: JudgeConfig,
) -> bool:
    return bool(
        config.second_model
        and primary.normalized
        and (
            primary.normalized.human_review_required
            or abs(primary.normalized.weighted_score - deterministic_score) > 20
        )
    )


def _prompt_hash(payload: dict[str, Any]) -> str:
    content = json.dumps(
        {"prompt_version": PROMPT_VERSION, "system_prompt": SYSTEM_PROMPT, "payload": payload},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode()).hexdigest()

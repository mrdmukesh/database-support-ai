from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from legacydb_copilot.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationRunModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    application_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    application_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    configuration_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timing_cost_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class TestScenarioModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_scenarios"
    scenario_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scenario_version: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    database_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    database_version: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    scripts_json: Mapped[str] = mapped_column(Text, nullable=False)
    expectations_json: Mapped[str] = mapped_column(Text, nullable=False)
    expected_response_type: Mapped[str] = mapped_column(String(60), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    __table_args__ = (
        UniqueConstraint("scenario_id", "scenario_version", name="uq_test_scenario_version"),
    )


class ScenarioExpectedObjectModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_expected_objects"
    test_scenario_id: Mapped[str] = mapped_column(
        ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)


class ScenarioExpectedEvidenceModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_expected_evidence"
    test_scenario_id: Mapped[str] = mapped_column(
        ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_key: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ScenarioAcceptableFixModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_acceptable_fixes"
    test_scenario_id: Mapped[str] = mapped_column(
        ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept: Mapped[str] = mapped_column(Text, nullable=False)


class EvaluationInvestigationResultModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_results"
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_scenario_id: Mapped[str] = mapped_column(
        ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    response_type: Mapped[str] = mapped_column(String(60), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)


class InvestigationEvidenceSnapshotModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_evidence_snapshots"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class InvestigationSQLSnapshotModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_sql_snapshots"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(60), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class DeterministicValidationResultModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deterministic_validation_results"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    validator_name: Mapped[str] = mapped_column(String(160), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score_component: Mapped[str] = mapped_column(String(80), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    critical_failures_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class AIJudgeResultModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_judge_results"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class HumanReviewModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "human_reviews"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    disposition: Mapped[str] = mapped_column(String(60), nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class CapabilityResultModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capability_results"
    investigation_result_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class EvaluationMetricModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_metrics"
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=True, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    dimensions_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class EvaluationArtifactModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_artifacts"
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("investigation_results.id", ondelete="CASCADE"), nullable=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(700), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class EvaluationScenarioExecutionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only final record for one scenario attempt within an evaluation run."""

    __tablename__ = "evaluation_scenario_executions"
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_scenario_id: Mapped[str] = mapped_column(
        ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scenario_version: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    database_version: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    investigation_id: Mapped[str] = mapped_column(
        String(80), default="", nullable=False, index=True
    )
    investigation_status: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    raw_request_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    raw_response_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timing_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    usage_cost_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    errors_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovery_artifact: Mapped[str] = mapped_column(String(700), default="", nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id", "scenario_id", "attempt", name="uq_eval_scenario_attempt"
        ),
    )


class EvaluationDeterministicScoreModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable deterministic validation version for a runner execution."""

    __tablename__ = "evaluation_deterministic_scores"
    scenario_execution_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_scenario_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause_correctness: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    evidence_correctness: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    object_discovery: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    fix_correctness: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    citation_correctness: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    safety: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    completeness: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    unadjusted_score: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    final_score: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    critical_failure: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "scenario_execution_id",
            "validation_version",
            name="uq_deterministic_score_version",
        ),
    )


class EvaluationAIJudgeScoreModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only AI judge invocation and normalized semantic score."""

    __tablename__ = "evaluation_ai_judge_scores"
    deterministic_score_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_deterministic_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_execution_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_scenario_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    judge_version: Mapped[int] = mapped_column(Integer, nullable=False)
    judge_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    prompt_json: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_response_json: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_result_json: Mapped[str] = mapped_column(Text, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    deterministic_difference: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "deterministic_score_id",
            "judge_version",
            "judge_index",
            name="uq_ai_judge_score_version",
        ),
    )


class EvaluationHumanReviewFlagModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only human-review decision for a judge version."""

    __tablename__ = "evaluation_human_review_flags"
    deterministic_score_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_deterministic_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    judge_version: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    random_sampled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deterministic_critical_failure: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "deterministic_score_id",
            "judge_version",
            name="uq_human_review_flag_version",
        ),
    )

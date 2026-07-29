from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GroundTruthStatus(StrEnum):
    REVIEWED = "REVIEWED"
    NEEDS_GROUND_TRUTH_REVIEW = "NEEDS_GROUND_TRUTH_REVIEW"


class ScenarioClassification(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_GROUND_TRUTH_REVIEW = "NEEDS_GROUND_TRUTH_REVIEW"
    EXECUTION_FAILED = "EXECUTION_FAILED"


@dataclass(frozen=True)
class BenchmarkManifestEntry:
    scenario_id: str
    database: str
    domain: str
    question: str


@dataclass(frozen=True)
class ProtectedGroundTruth:
    scenario_id: str
    review_status: GroundTruthStatus
    expected_entities: tuple[str, ...] = ()
    expected_objects: tuple[str, ...] = ()
    expected_evidence: tuple[str, ...] = ()
    expected_findings: tuple[str, ...] = ()
    expected_recommendations: tuple[str, ...] = ()
    expected_terminal_states: tuple[str, ...] = ()
    expected_root_cause_status: str = ""
    allowed_domains: tuple[str, ...] = ()


@dataclass
class AgenticScenarioCapture:
    scenario_id: str
    database: str
    domain: str
    question: str
    investigation_id: str = ""
    terminal_state: str = ""
    evidence_status: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    sql: list[str] = field(default_factory=list)
    sql_count: int = 0
    verified_absence: list[dict[str, Any]] = field(default_factory=list)
    failed_actions: list[dict[str, Any]] = field(default_factory=list)
    blocked_actions: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    verified_claims: list[dict[str, Any]] = field(default_factory=list)
    rejected_claims: list[dict[str, Any]] = field(default_factory=list)
    root_cause_status: str = ""
    fix_readiness: str = ""
    identified_entities: list[str] = field(default_factory=list)
    discovered_objects: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    validation_tests: list[str] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    evidence_facts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    report_json: dict[str, Any] = field(default_factory=dict)
    report_pdf: str = ""
    duration_seconds: float = 0
    stop_reason: str = ""
    polling_diagnostics: dict[str, Any] = field(default_factory=dict)
    lifecycle_diagnostics: dict[str, Any] = field(default_factory=dict)
    execution_error: str = ""
    wrong_investigation_data: bool = False


@dataclass(frozen=True)
class CategoryScores:
    entity_object_selection: float
    evidence_collection: float
    evidence_verification: float
    finding_accuracy: float
    root_cause_discipline: float
    recommendation_test_quality: float
    citation_report_integrity: float

    @property
    def total(self) -> float:
        return round(
            self.entity_object_selection
            + self.evidence_collection
            + self.evidence_verification
            + self.finding_accuracy
            + self.root_cause_discipline
            + self.recommendation_test_quality
            + self.citation_report_integrity,
            3,
        )


@dataclass(frozen=True)
class AgenticScenarioResult:
    capture: AgenticScenarioCapture
    classification: ScenarioClassification
    ground_truth_status: GroundTruthStatus
    scores: CategoryScores
    automatic_failures: tuple[str, ...]
    defects: tuple[str, ...]

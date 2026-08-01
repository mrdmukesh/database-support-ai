from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AccuracyGroundTruth:
    """Reviewed expectations that are never supplied to the investigation runtime."""

    scenario_id: str
    expected_entity: str
    expected_database: str
    expected_tables: tuple[str, ...]
    expected_sql_evidence: tuple[str, ...]
    expected_reproduction_status: str
    expected_root_cause: str | None
    expected_evidence: tuple[str, ...]
    expected_gaps: tuple[str, ...]
    expected_corrective_action_boundaries: tuple[str, ...]
    forbidden_claims: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AccuracyGroundTruth:
        required = {
            "scenario_id",
            "expected_entity",
            "expected_database",
            "expected_tables",
            "expected_sql_evidence",
            "expected_reproduction_status",
            "expected_root_cause",
            "expected_evidence",
            "expected_gaps",
            "expected_corrective_action_boundaries",
            "forbidden_claims",
        }
        missing = sorted(required - value.keys())
        if missing:
            raise ValueError(f"Missing accuracy ground-truth fields: {', '.join(missing)}")
        status = str(value["expected_reproduction_status"]).strip().casefold()
        if status not in {"reproduced", "not_reproduced", "insufficient_evidence"}:
            raise ValueError("expected_reproduction_status is invalid")
        return cls(
            scenario_id=_required("scenario_id", value["scenario_id"]),
            expected_entity=_required("expected_entity", value["expected_entity"]),
            expected_database=_required("expected_database", value["expected_database"]),
            expected_tables=_strings(value["expected_tables"]),
            expected_sql_evidence=_strings(value["expected_sql_evidence"]),
            expected_reproduction_status=status,
            expected_root_cause=(
                str(value["expected_root_cause"]).strip()
                if value["expected_root_cause"] is not None
                else None
            ),
            expected_evidence=_strings(value["expected_evidence"]),
            expected_gaps=_strings(value["expected_gaps"]),
            expected_corrective_action_boundaries=_strings(
                value["expected_corrective_action_boundaries"]
            ),
            forbidden_claims=_strings(value["forbidden_claims"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccuracyValidationResult:
    scenario_id: str
    deterministic_score: float
    component_scores: dict[str, float]
    automatic_failure: bool
    failure_reasons: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    hallucination_findings: tuple[str, ...]
    evidence_coverage: float
    sql_coverage: float
    checks: dict[str, bool]
    recommendation: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _required(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("Ground-truth collection fields must be arrays")
    return tuple(str(item).strip() for item in value if str(item).strip())

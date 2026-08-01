from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.state import InvestigationState


@dataclass(frozen=True)
class ReportingAdapter:
    compose: Callable[[InvestigationState], dict[str, Any]]
    deterministic_compose: Callable[[InvestigationState], dict[str, Any]]

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        use_reasoning = bool(
            state["reasoning_result"]
            and state["reasoning_persisted"]
            and not state["reasoning_validation_errors"]
        )
        report = self.compose(state) if use_reasoning else self.deterministic_compose(state)
        sanitized = sanitize_ai_trace(report)
        if not isinstance(sanitized, dict):
            raise OperationalNodeError("REPORT_COMPOSITION_FAILED", "Report was not structured.")
        return {"structured_report": sanitized}


@dataclass(frozen=True)
class ReportValidationAdapter:
    validate: Callable[[dict[str, Any], InvestigationState], list[str]]
    persist: Callable[[InvestigationState, dict[str, Any]], list[str]]

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        report = state["structured_report"]
        if report is None:
            return {
                "report_validation_errors": ["Structured report is missing."],
                "quality_review_required": True,
            }
        errors = self.validate(report, state)
        if errors:
            return {
                "report_validation_errors": errors,
                "quality_review_required": True,
                "report_artifact_ids": [],
            }
        try:
            artifacts = self.persist(state, report)
        except Exception as exc:
            raise OperationalNodeError(
                "REPORT_PERSISTENCE_FAILED",
                "Validated report could not be persisted.",
                context={"detail": str(exc)},
            ) from exc
        return {
            "report_validation_errors": [],
            "quality_review_required": state["quality_review_required"],
            "report_artifact_ids": list(dict.fromkeys(artifacts)),
        }

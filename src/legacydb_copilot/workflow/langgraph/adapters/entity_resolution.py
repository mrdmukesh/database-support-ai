from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import (
    EntityExtractionResult,
    ExtractedEntity,
    extract_entities,
)
from legacydb_copilot.services.entity_resolution_service import (
    EntityResolutionResult,
    resolve_entities,
)
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    WorkflowTerminalStatus,
)
from legacydb_copilot.workflow.langgraph.state import (
    EntityCandidateRecord,
    InvestigationState,
    ResolvedEntityRecord,
)

AuthorizationGuard = Callable[[InvestigationState], None]
MetadataProvider = Callable[[InvestigationState], MetadataSearchResult]
Resolver = Callable[[Any, MetadataSearchResult, EntityExtractionResult], EntityResolutionResult]


@dataclass(frozen=True)
class EntityResolutionAdapter:
    """Translate the existing resolver result into workflow state updates."""

    connector: Any
    metadata_provider: MetadataProvider
    authorize: AuthorizationGuard
    resolver: Resolver = resolve_entities
    extractor: Callable[[str], EntityExtractionResult] = extract_entities
    provider_assisted_ranking: bool = False

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if self.provider_assisted_ranking:
            raise OperationalNodeError(
                "ENTITY_PROVIDER_RANKING_DISABLED",
                "Provider-assisted entity ranking is disabled for this workflow.",
            )
        try:
            self.authorize(state)
            metadata = self.metadata_provider(state)
            entities = self._entities(state)
            result = self.resolver(self.connector, metadata, entities)
        except PermissionError as exc:
            raise OperationalNodeError(
                "WORKSPACE_ACCESS_DENIED",
                "Workspace authorization denied entity resolution.",
                context={"workspace_id": state["workspace_id"], "detail": str(exc)},
            ) from exc
        except OperationalNodeError:
            raise
        except Exception as exc:
            raise OperationalNodeError(
                "ENTITY_RESOLUTION_UNAVAILABLE",
                "Entity resolution service is temporarily unavailable.",
                retryable=True,
                context={"workspace_id": state["workspace_id"], "detail": str(exc)},
            ) from exc

        candidates: list[EntityCandidateRecord] = []
        resolved: list[ResolvedEntityRecord] = []
        explanations: list[str] = []
        ambiguities: list[str] = []
        methods: list[str] = []
        for resolution in result.resolutions:
            methods.append(resolution.match_type)
            if resolution.reason:
                explanations.append(resolution.reason)
            for rank, candidate in enumerate(resolution.candidates, 1):
                candidates.append(
                    EntityCandidateRecord(
                        entity_type="business_identifier",
                        business_key=resolution.extracted_value,
                        matched_value=candidate.identifier,
                        table=candidate.table,
                        column=candidate.column,
                        matching_method=resolution.match_type,
                        deterministic_rank=rank,
                        confidence=resolution.confidence,
                        verified=bool(candidate.evidence_id),
                        evidence_id=candidate.evidence_id,
                    )
                )
            if resolution.matched_value:
                resolved.append(
                    ResolvedEntityRecord(
                        entity_type="business_identifier",
                        business_key=resolution.extracted_value,
                        matched_value=resolution.matched_value,
                        table=resolution.resolved_table,
                        column=resolution.resolved_column,
                        matching_method=resolution.match_type,
                        deterministic_rank=1,
                        confidence=resolution.confidence,
                        evidence_id=resolution.evidence_id,
                    )
                )
            elif resolution.match_type == "ambiguous":
                ambiguities.append(resolution.extracted_value)

        status = {
            "resolved": EntityResolutionStatus.RESOLVED,
            "ambiguous": EntityResolutionStatus.AMBIGUOUS,
            "not_found": EntityResolutionStatus.NOT_FOUND,
            "blocked": EntityResolutionStatus.BLOCKED,
        }.get(result.status, EntityResolutionStatus.FAILED)
        terminal = {
            EntityResolutionStatus.AMBIGUOUS: WorkflowTerminalStatus.AMBIGUOUS_ENTITY,
            EntityResolutionStatus.NOT_FOUND: WorkflowTerminalStatus.ENTITY_NOT_FOUND,
        }.get(status, state["terminal_status"])
        return {
            "entity_resolution_status": status,
            "resolved_entities": resolved,
            "entity_candidates": candidates,
            "entity_resolution_method": ", ".join(dict.fromkeys(methods)),
            "entity_resolution_explanation": " ".join(dict.fromkeys(explanations)),
            "entity_ambiguities": ambiguities,
            "terminal_status": terminal,
        }

    def _entities(self, state: InvestigationState) -> EntityExtractionResult:
        if state["requested_entity"].strip():
            return EntityExtractionResult(
                [ExtractedEntity("business_identifier", state["requested_entity"].strip())],
                None,
                None,
            )
        return self.extractor(state["question"])

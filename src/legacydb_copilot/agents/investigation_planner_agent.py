from __future__ import annotations

from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery, plan_safe_queries


def build_investigation_plan(
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    debug_events: list[dict[str, Any]] | None = None,
) -> list[PlannedQuery]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles build investigation plan within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation orchestration in routers/chat.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return plan_safe_queries(intent, metadata, entities, debug_events=debug_events)

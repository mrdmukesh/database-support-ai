from __future__ import annotations

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery, plan_safe_queries


def build_investigation_plan(intent: InvestigationIntent, metadata: MetadataSearchResult, entities: EntityExtractionResult) -> list[PlannedQuery]:
    return plan_safe_queries(intent, metadata, entities)

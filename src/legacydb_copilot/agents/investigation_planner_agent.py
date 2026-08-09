from __future__ import annotations

import re
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.safe_sql_service import PlannedQuery, plan_safe_queries

RCA_INVESTIGATION_POLICY_VERSION = "evidence-first-generic-sqlserver-v1"


def _identifier_terms(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", expanded)
        if len(token) > 1
    }


def _internal_plan(
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    queries: list[PlannedQuery],
) -> dict[str, Any]:
    """Build an auditable, database-derived plan before evidence execution."""
    entity_values = [
        {"type": item.entity_type, "value": item.value}
        for item in entities.entities
    ]
    requested_terms: set[str] = set()
    for item in entities.entities:
        requested_terms.update(_identifier_terms(item.value))
    for keyword in entities.business_keywords or []:
        requested_terms.update(_identifier_terms(keyword))

    candidate_tables: list[dict[str, Any]] = []
    candidate_columns: list[dict[str, Any]] = []
    for rank, table in enumerate(metadata.tables, start=1):
        relationship_count = len(table.foreign_keys or [])
        candidate_tables.append(
            {
                "rank": rank,
                "name": table.name,
                "reason": (
                    "Ranked by discovered metadata relevance; entity-row evidence is still required"
                    + (
                        f"; {relationship_count} foreign-key relationship(s) available"
                        if relationship_count
                        else ""
                    )
                ),
                "requires_entity_row_verification": True,
            }
        )
        for column in table.columns:
            overlap = _identifier_terms(column) & requested_terms
            if overlap:
                candidate_columns.append(
                    {
                        "table": table.name,
                        "column": column,
                        "reason": f"Matches requested concept(s): {', '.join(sorted(overlap))}",
                        "requires_value_or_derivation_verification": True,
                    }
                )

    candidate_procedures = [
        {
            "name": procedure,
            "reason": "Discovered metadata candidate; name similarity alone is insufficient",
            "requires_definition_or_dependency_verification": True,
        }
        for procedure in metadata.procedures
    ]
    return {
        "event": "internal_investigation_plan",
        "policy_version": RCA_INVESTIGATION_POLICY_VERSION,
        "intent": intent.value,
        "candidate_entities": entity_values,
        "affected_attribute_candidates": candidate_columns,
        "candidate_tables": candidate_tables,
        "candidate_procedures": candidate_procedures,
        "relationship_sources": [
            "primary_keys",
            "foreign_keys",
            "indexes",
            "views",
            "routine_dependencies",
            "triggers",
        ],
        "verification_queries": [
            {"purpose": query.purpose, "sql": query.sql}
            for query in queries
        ],
        "evidence_gate": (
            "Do not finalize a root cause until entity, attribute, object reference, "
            "and symptom evidence are verified."
        ),
        "ranking_order": [
            "actual matching entity row",
            "direct affected column",
            "direct procedure/table reference",
            "foreign-key/dependency relationship",
            "business metadata",
            "semantic similarity",
        ],
    }


def build_investigation_plan(
    intent: InvestigationIntent,
    metadata: MetadataSearchResult,
    entities: EntityExtractionResult,
    debug_events: list[dict[str, Any]] | None = None,
    *,
    provider: Any | None = None,
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
    plan = plan_safe_queries(
        intent,
        metadata,
        entities,
        debug_events=debug_events,
        provider=provider,
    )
    if debug_events is not None:
        debug_events.append(_internal_plan(intent, metadata, entities, plan))
    return plan

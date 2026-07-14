from __future__ import annotations

from dataclasses import dataclass

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.services.diagnostic_object_service import is_diagnostic_object
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.problem_phrase_service import parse_problem_phrase, resolve_table_from_terms

_NOISE_TOKENS = {
    "analyze",
    "explain",
    "index",
    "indexes",
    "logic",
    "optimization",
    "recommend",
    "row",
    "rows",
    "scan",
    "scans",
    "stored",
    "procedure",
}

_KNOWLEDGE_OBJECT_MARKERS = {
    "approved_knowledge",
    "document_chunk",
    "embedding",
    "incident_knowledge",
    "knowledge_base",
    "rag_document",
}


@dataclass(frozen=True)
class RankedObject:
    object_type: str
    name: str
    score: float
    reason: str


@dataclass(frozen=True)
class ObjectRankingResult:
    objects: list[RankedObject]
    metadata: MetadataSearchResult


def _is_knowledge_object(name: str) -> bool:
    """Keep retrieval infrastructure out of live affected-object ranking."""
    normalized = name.lower().replace("-", "_").replace(".", "_")
    return any(marker in normalized for marker in _KNOWLEDGE_OBJECT_MARKERS)


def _tokens(question: str, entities: EntityExtractionResult) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for tokens within object_ranking_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in object_ranking_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    tokens = {token.strip(".,:;()[]{}").lower() for token in question.replace("_", " ").replace("-", " ").split()}
    tokens = {token for token in tokens if len(token) >= 3 and token not in _NOISE_TOKENS}
    for entity in entities.entities:
        tokens.update(
            part.lower()
            for part in entity.value.replace("-", " ").split()
            if len(part) >= 3 and part.lower() not in _NOISE_TOKENS
        )
    if entities.likely_module:
        tokens.add(entities.likely_module.lower())
    if entities.suspected_issue:
        tokens.update(entities.suspected_issue.lower().split())
    return tokens


def _intent_bonus(intent: InvestigationIntent, table: TableMetadata) -> float:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for intent bonus within object_ranking_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in object_ranking_agent.py.
    
    Where it fits in the flow:
        Question/context -> agent reasoning step -> structured output for downstream services.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    name = table.name.lower()
    columns = " ".join(table.columns).lower()
    text = f"{name} {columns}"
    has_history_or_log = any(term in text for term in ("batch", "job", "history", "log", "audit", "run", "error"))
    has_business_key = any(col.lower().endswith(("_number", "_code", "_ref", "_key")) for col in table.columns)
    has_status = any(term in columns for term in ("status", "state", "stage"))
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION and (has_history_or_log or table.indexes):
        return 1.5
    if intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION} and has_business_key:
        return 1.5
    if intent == InvestigationIntent.MISSING_DATA and (table.foreign_keys or has_status):
        return 1.2
    if intent == InvestigationIntent.PROCESS_FLOW_BREAK and any(term in text for term in ("status", "state", "flow", "audit", "history")):
        return 1.2
    if intent == InvestigationIntent.FAILED_BATCH_JOB and any(term in text for term in ("batch", "job", "run", "error", "log")):
        return 1.8
    return 0.0


def rank_relevant_objects(
    *,
    question: str,
    intent: IntentResult,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    max_tables: int = 6,
) -> ObjectRankingResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles rank relevant objects within the Database Support AI application flow.
    
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
    tokens = _tokens(question, entities)
    problem = parse_problem_phrase(question)
    target_table = resolve_table_from_terms(problem.target_terms, metadata)
    parent_table = resolve_table_from_terms(problem.parent_terms, metadata)
    ranked_tables: list[tuple[float, TableMetadata, str]] = []
    eligible_tables = [table for table in metadata.tables if not _is_knowledge_object(table.name)]
    for table in eligible_tables:
        haystack_items = [table.name, *table.columns]
        haystack = " ".join(haystack_items).lower()
        token_hits = sum(1 for token in tokens if token in haystack)
        relationship_bonus = 0.5 if table.foreign_keys else 0.0
        index_bonus = 0.25 if table.indexes else 0.0
        score = float(table.score) + token_hits + relationship_bonus + index_bonus + _intent_bonus(intent.intent, table)
        reason = f"Matched {token_hits} question/entity token(s)"
        if target_table and table.name == target_table.name:
            score += 12.0
            reason += "; selected from main problem phrase target"
        elif parent_table and table.name == parent_table.name:
            score += 4.0
            reason += "; selected from main problem phrase parent"
        if relationship_bonus:
            reason += "; has foreign-key relationships"
        if index_bonus:
            reason += "; has indexes"
        if score > 0:
            ranked_tables.append((score, table, reason))
    ranked_tables.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    selected_tables = [table for _, table, _ in ranked_tables[:max_tables]]
    for required in (target_table, parent_table):
        if required and required.name not in {table.name for table in selected_tables}:
            selected_tables = [required, *selected_tables[: max_tables - 1]]
    if intent.intent == InvestigationIntent.MISSING_DATA:
        for table in eligible_tables:
            if table.name in {item.name for item in selected_tables}:
                continue
            if is_diagnostic_object(table.name):
                selected_tables.append(table)
            if len(selected_tables) >= max_tables + 4:
                break
    selected_names = {table.name for table in selected_tables}
    if not selected_tables:
        selected_tables = eligible_tables[:max_tables]
        selected_names = {table.name for table in selected_tables}

    proc_tokens = tokens | {table.name.lower() for table in selected_tables}
    procedures = [
        proc
        for proc in metadata.procedures
        if not _is_knowledge_object(proc) and any(token in proc.lower() for token in proc_tokens)
    ]
    eligible_views = [view for view in metadata.views if not _is_knowledge_object(view)]
    views = [view for view in eligible_views if any(token in view.lower() for token in proc_tokens)]
    if not views:
        views = eligible_views[:5]

    objects = [
        RankedObject("table", table.name, score, reason)
        for score, table, reason in ranked_tables
        if table.name in selected_names
    ]
    objects.extend(RankedObject("procedure", proc, 1.0, "Procedure name matched selected object or question tokens") for proc in procedures)
    objects.extend(RankedObject("view", view, 0.8, "View name matched relevant tokens or retained for context") for view in views)
    selected_for_trace = {table.name for table in selected_tables}
    selected_for_trace.update(procedures)
    candidate_trace = [
        {
            **item,
            "decision": "selected" if item.get("name") in selected_for_trace else "rejected",
            **(
                {"rejection_reason": "knowledge objects cannot be affected business objects"}
                if item.get("object_type") == "table" and _is_knowledge_object(str(item.get("name", "")))
                else {}
            ),
        }
        if item.get("object_type") == "table"
        else item
        for item in metadata.candidate_trace
    ]
    return ObjectRankingResult(
        objects=objects,
        metadata=MetadataSearchResult(
            tables=selected_tables,
            views=views,
            procedures=procedures,
            version=metadata.version,
            engine_type=metadata.engine_type,
            candidate_trace=candidate_trace,
        ),
    )

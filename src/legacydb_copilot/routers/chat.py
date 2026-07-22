from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, replace
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from legacydb_copilot.ai import SafetyFinding, analyze_prompt
from legacydb_copilot.agents.context_discovery_agent import discover_context
from legacydb_copilot.agents.entity_extraction_agent import ExtractedEntity, extract_entities
from legacydb_copilot.agents.hypothesis_agent import run_hypothesis_investigation
from legacydb_copilot.agents.intent_agent import InvestigationIntent, detect_intent
from legacydb_copilot.agents.investigation_planner_agent import build_investigation_plan
from legacydb_copilot.agents.object_ranking_agent import rank_relevant_objects
from legacydb_copilot.agents.recommendation_agent import recommend_actions
from legacydb_copilot.agents.reasoning_agent import reason_about_evidence
from legacydb_copilot.agents.report_composer_agent import compose_report
from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.config import Settings
from legacydb_copilot.db.connector import DatabaseConnectionError, get_connection_pool
from legacydb_copilot.db.models import (
    ChatConversationModel,
    ChatMessageModel,
    DatabaseConnectionModel,
    DocumentModel,
    InvestigationModel,
    VerificationCheckModel,
    WorkspaceModel,
)
from legacydb_copilot.dependencies import assert_same_organization, assert_same_user, require_permission
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.routers.databases import _build_connection_string
from legacydb_copilot.reports.dynamic_report_schema import DynamicInvestigationBundle
from legacydb_copilot.schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatConversationRead,
    ChatMessageRead,
    VerificationCheckRead,
    VerificationRunAllResponse,
    VerificationRunRequest,
)
from legacydb_copilot.security.access_control import (
    require_resource_owner_workspace,
    require_workspace_access,
)
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.confidence_scoring_service import confidence_factors, score_confidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult, execute_evidence_plan
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate, unreproduced_reasoning
from legacydb_copilot.services.evidence_verification_agent import execute_verification_check, suggest_verification_checks
from legacydb_copilot.services.entity_resolution_service import (
    EntityResolutionResult,
    metadata_with_resolved_tables,
    resolution_metadata_for_schema,
    resolve_entities,
)
from legacydb_copilot.services.diagnostic_object_service import is_diagnostic_object
from legacydb_copilot.services.investigation_reports import (
    generate_investigation_report_files,
    report_storage_references,
)
from legacydb_copilot.services.investigation_mode_service import (
    InvestigationMode,
    ModeClassification,
    classify_investigation_mode,
)
from legacydb_copilot.services.llm_reasoning_service import (
    AI_REASONING_PROMPT_VERSION,
    enhance_reasoning_with_llm,
    llm_reasoning_enabled,
)
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchContext,
    query_relevance_terms,
    resolve_qualified_object_names,
)
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace
from legacydb_copilot.services.problem_phrase_service import parse_problem_phrase, resolve_table_from_terms
from legacydb_copilot.services.rag_retrieval_service import KnowledgeQuery, get_knowledge_retriever
from legacydb_copilot.services.report_generator import (
    ExecutiveSummary,
    InvestigationReport,
    ReportCover,
    ReportSection,
    ReportTable,
    REPORT_VERSION,
    new_investigation_id,
    now_label,
)
from legacydb_copilot.services.report_snapshot_service import report_from_dict, report_to_dict
from legacydb_copilot.services.stored_procedure_intelligence import analyze_stored_procedures
from legacydb_copilot.services.transfer_identifier_normalization import normalize_transfer_entities

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _definition_relevant_procedures(connector, procedure_names: list[str], relevance_terms: set[str]) -> list[str]:
    """Select procedure names/definitions using only normalized terms derived from the current request."""
    def identifier_terms(value: str) -> set[str]:
        expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
        return {part.lower() for part in re.findall(r"[A-Za-z][A-Za-z0-9]*", expanded) if len(part) >= 2}

    matched: list[str] = []
    for procedure_name in procedure_names:
        try:
            definition = connector.get_procedure_definition(procedure_name) or ""
        except Exception:
            definition = ""
        if relevance_terms & (identifier_terms(procedure_name) | identifier_terms(definition)):
            matched.append(procedure_name)
    return list(dict.fromkeys(matched))


def _investigation_status(detected_intent: object, answer_provenance: object = None) -> str:
    if answer_provenance:
        return str(answer_provenance)
    return (
        "INSUFFICIENT_DATABASE_EVIDENCE"
        if str(detected_intent or "").startswith("INSUFFICIENT_DATABASE_EVIDENCE:")
        else "AI_ANSWERED"
    )


def _title_from_question(question: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for title from question within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    clean = " ".join(question.strip().split())
    return clean[:72] or "New conversation"


def _build_placeholder_answer(question: str, findings: tuple[SafetyFinding, ...]) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for build placeholder answer within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if SafetyFinding.PROMPT_INJECTION in findings:
        return (
            "I detected prompt-injection language. I cannot follow instructions that try to "
            "bypass safety rules, reveal hidden prompts, or ignore system policy. Rephrase the "
            "database support question using the actual issue, object names, error text, and what "
            "you already validated."
        )
    if SafetyFinding.UNSAFE_SQL in findings:
        return (
            "I detected potentially unsafe SQL. Do not execute this in production. A DBA or senior "
            "developer must review the statement, confirm backups and rollback steps, and validate "
            "the WHERE clause or destructive operation before any change."
        )
    return (
        "MVP placeholder answer: I would investigate this by checking the workspace documents, "
        "extracted database metadata, recent incidents, and known dependency notes. Validate any SQL "
        "manually before execution. Question received: "
        f"{question.strip()}"
    )


def _sql_block(sql: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for sql block within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return "```sql\n" + sql.strip() + "\n```"


def _evidence_sql_block(item) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for evidence sql block within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    if not getattr(item, "safety_note", None):
        return _sql_block(item.sql)
    return (
        "Original:\n"
        + _sql_block(getattr(item, "original_sql", None) or item.sql)
        + "\nModified for safety:\n"
        + _sql_block(item.sql)
        + f"\nReason: {item.safety_note}"
    )



def _find_workspace_connection(db: Session, payload: ChatAskRequest) -> DatabaseConnectionModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for find workspace connection within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    connection_id = (payload.connection_id or "").strip()
    if not connection_id:
        raise HTTPException(status_code=400, detail="connection_id is required for investigation submission")
    connection = db.get(DatabaseConnectionModel, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Selected database connection was not found")
    if connection.organization_id != payload.organization_id or connection.workspace_id != payload.workspace_id:
        raise HTTPException(status_code=400, detail="Selected database connection does not belong to the requested workspace")
    if not connection.is_active:
        raise HTTPException(status_code=400, detail="Selected database connection is inactive")
    return connection


def _connection_string_database(connection_string: str) -> str:
    try:
        return make_url(connection_string).database or ""
    except Exception:
        return ""


def _metadata_context_for_connection(
    payload: ChatAskRequest,
    connection: DatabaseConnectionModel,
    connection_string: str,
    *,
    actual_database: str = "",
    connector_cache_key: str = "",
) -> MetadataSearchContext:
    database_name = connection.database_name or _connection_string_database(connection_string) or connection.name
    return MetadataSearchContext(
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        connection_id=connection.id,
        database_name=database_name,
        schema_name="",
        connection_string_database=_connection_string_database(connection_string),
        actual_database=actual_database,
        connector_cache_key=connector_cache_key,
    )


def _active_database_name(connector, expected_engine: DatabaseEngine) -> str:
    if expected_engine != DatabaseEngine.MYSQL:
        return ""
    rows = connector.execute_read_only_query("SELECT DATABASE() AS active_database", limit=1)
    if not rows:
        return ""
    row = rows[0]
    return str(row.get("active_database") or row.get("DATABASE()") or next(iter(row.values()), "") or "")


def _load_and_validate_active_schema(connector, metadata_context: MetadataSearchContext, expected_engine: DatabaseEngine):
    actual_database = _active_database_name(connector, expected_engine)
    if actual_database and metadata_context.connection_string_database and actual_database.lower() != metadata_context.connection_string_database.lower():
        raise DatabaseConnectionError(
            "Active database validation failed: "
            f"expected_database={metadata_context.connection_string_database}; actual_database={actual_database}"
        )
    if actual_database:
        metadata_context = MetadataSearchContext(
            organization_id=metadata_context.organization_id,
            workspace_id=metadata_context.workspace_id,
            connection_id=metadata_context.connection_id,
            database_name=metadata_context.database_name,
            schema_name=metadata_context.schema_name,
            connection_string_database=metadata_context.connection_string_database,
            actual_database=actual_database,
            connector_cache_key=metadata_context.connector_cache_key,
        )
    force_refresh = os.getenv("EVAL_FORCE_METADATA_REFRESH", "false").lower() in {"1", "true", "yes", "on"}
    try:
        metadata = connector.get_schema_metadata(force_refresh=force_refresh)
    except TypeError:  # compatibility for connector test doubles and older plugins
        metadata = connector.get_schema_metadata()
    logger.info(
        "RCA metadata context workspace_id=%s connection_id=%s database=%s schema=%s engine=%s "
        "connection_string_database=%s metadata_cache_key=%s tables=%s procedures=%s",
        metadata_context.workspace_id,
        metadata_context.connection_id,
        metadata_context.database_name,
        metadata_context.schema_name or "default",
        metadata.engine_type,
        metadata_context.connection_string_database or "unknown",
        metadata_context.cache_key,
        metadata.tables,
        metadata.procedures,
    )
    if not metadata.tables:
        raise DatabaseConnectionError(
            "Active database metadata validation failed: no tables were discovered for the selected connection."
        )
    return metadata, metadata_context


def _target_object_not_found_metadata_answer(
    *,
    payload: ChatAskRequest,
    connection: DatabaseConnectionModel,
    metadata,
    metadata_context: MetadataSearchContext,
    active_schema_metadata,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    trace_lines = [
        "TARGET_OBJECT_NOT_FOUND",
        f"workspace_id={payload.workspace_id}",
        f"connection_id={connection.id}",
        f"expected_database={metadata_context.connection_string_database or metadata_context.database_name}",
        f"actual_database={metadata_context.actual_database or 'unknown'}",
        f"database_engine={metadata.engine_type or connection.engine}",
        f"connector_cache_key={metadata_context.connector_cache_key}",
        f"metadata_cache_key={metadata.metadata_cache_key or metadata_context.cache_key}",
        f"exact_tables_requested={metadata.exact_tables_requested}",
        f"exact_tables_found={metadata.exact_tables_found}",
        f"exact_procedures_requested={metadata.exact_procedures_requested}",
        f"exact_procedures_found={metadata.exact_procedures_found}",
        f"failure_reason={metadata.failure_reason}",
        f"Discovered tables={active_schema_metadata.tables}",
        f"Discovered procedures={active_schema_metadata.procedures}",
    ]
    answer = (
        "TARGET_OBJECT_NOT_FOUND\n\n"
        "The investigation was stopped because an explicitly requested table or procedure was not found "
        "in the active database metadata. I did not fall back to semantic alternatives or stale metadata.\n\n"
        + "\n".join(f"- {line}" for line in trace_lines)
    )
    investigation_metadata = _empty_investigation_metadata()
    investigation_metadata["detected_intent"] = "TARGET_OBJECT_NOT_FOUND"
    investigation_metadata["evidence"] = "[]"
    investigation_metadata["sql_queries"] = "[]"
    investigation_metadata["report_snapshot"] = ""
    return answer, [connection.name, "active metadata validation"], 0.1, None, investigation_metadata


def _run_metadata_validation(
    db: Session,
    payload: ChatAskRequest,
    intent,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    connection = _find_workspace_connection(db, payload)
    if connection is None:
        return (
            "TARGET_OBJECT_NOT_FOUND\n\nNo active database connection is configured for this workspace.",
            [],
            0.1,
            None,
            _empty_investigation_metadata(),
        )
    try:
        connection_string = _build_connection_string(connection)
        engine = DatabaseEngine(connection.engine)
        pool = get_connection_pool()
        connector_cache_key = pool.connector_cache_key(engine, connection_string)
        connector = pool.get_or_create(connection.id, engine, connection_string)
        connector.connect()
        metadata_context = _metadata_context_for_connection(
            payload,
            connection,
            connection_string,
            connector_cache_key=connector_cache_key,
        )
        active_schema_metadata, metadata_context = _load_and_validate_active_schema(connector, metadata_context, engine)
    except (DatabaseConnectionError, ValueError) as exc:
        return (
            "TARGET_OBJECT_NOT_FOUND\n\n"
            f"Active database validation failed before metadata lookup: {exc}",
            [connection.name],
            0.1,
            None,
            _empty_investigation_metadata(),
        )
    exact_tables = _explicit_metadata_names(payload.question, "table")
    exact_procedures = _explicit_metadata_names(payload.question, "procedure")
    resolved_tables = resolve_qualified_object_names(active_schema_metadata.tables, exact_tables)
    resolved_procedures = resolve_qualified_object_names(
        active_schema_metadata.procedures,
        exact_procedures,
    )
    table_results = {name: resolved_tables.get(name) for name in exact_tables}
    procedure_results = {name: resolved_procedures.get(name) for name in exact_procedures}
    missing_tables = [name for name, found in table_results.items() if not found]
    missing_procedures = [name for name, found in procedure_results.items() if not found]
    status_label = "TARGET_OBJECT_NOT_FOUND" if missing_tables or missing_procedures else "METADATA_VALIDATION_OK"
    answer = (
        f"{status_label}\n\n"
        "Live database metadata validation only. Uploaded documents, previous investigations, approved knowledge, ranking, LLM reasoning, and evidence gate were not used.\n\n"
        f"- active_database: {metadata_context.actual_database or metadata_context.connection_string_database or metadata_context.database_name}\n"
        f"- expected_database: {metadata_context.connection_string_database or metadata_context.database_name}\n"
        f"- connection_id: {connection.id}\n"
        f"- database_engine: {active_schema_metadata.engine_type}\n"
        f"- connector_cache_key: {metadata_context.connector_cache_key}\n"
        f"- metadata_cache_key: {metadata_context.cache_key}\n"
        f"- discovered_table_result: {table_results if table_results else 'No table requested'}\n"
        f"- discovered_procedure_result: {procedure_results if procedure_results else 'No procedure requested'}\n"
        f"- discovered_tables: {active_schema_metadata.tables}\n"
        f"- discovered_procedures: {active_schema_metadata.procedures}\n"
        f"- failure_reason: {'; '.join([*(f'table {name} not found' for name in missing_tables), *(f'procedure {name} not found' for name in missing_procedures)]) or 'none'}"
    )
    metadata = _empty_investigation_metadata()
    metadata["detected_intent"] = intent.intent.value
    metadata["evidence"] = "[]"
    metadata["sql_queries"] = "[]"
    return answer, [connection.name, "active database metadata"], 0.95 if status_label == "METADATA_VALIDATION_OK" else 0.1, None, metadata


def _explicit_metadata_names(question: str, label: str) -> list[str]:
    identifier = r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?"
    pattern = rf"\b{label}\s*:\s*({identifier})\b"
    names = [match.group(1) for match in re.finditer(pattern, question, re.I)]
    if names:
        return list(dict.fromkeys(names))
    if label == "table":
        match = re.search(rf"\btable\s+({identifier})\b", question, re.I)
    else:
        match = re.search(rf"\bprocedure\s+({identifier})\b", question, re.I)
    return [match.group(1)] if match else []



def _get_or_create_conversation(
    db: Session,
    payload: ChatAskRequest,
) -> ChatConversationModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for get or create conversation within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if payload.conversation_id:
        conversation = db.get(ChatConversationModel, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if (
            conversation.organization_id != payload.organization_id
            or conversation.workspace_id != payload.workspace_id
            or conversation.user_id != payload.user_id
        ):
            raise HTTPException(status_code=403, detail="Conversation is outside this tenant scope")
        return conversation

    workspace = db.get(WorkspaceModel, payload.workspace_id)
    if workspace is None or workspace.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")

    conversation = ChatConversationModel(
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        user_id=payload.user_id,
        title=_title_from_question(payload.question),
    )
    db.add(conversation)
    db.flush()
    return conversation


def _evidence_to_json(evidence) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for evidence to json within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    return json.dumps(
        [
            {
                "evidence_id": item.evidence_id,
                "purpose": getattr(item, "purpose", getattr(item, "title", "Evidence query")),
                "sql": item.sql,
                "row_count": len(item.rows),
                "sample_rows": item.rows[:10],
                "error": getattr(item, "error", None),
            }
            for item in evidence
        ],
        default=str,
    )


def _empty_investigation_metadata() -> dict[str, Any]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for empty investigation metadata within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return {
        "investigation_id": None,
        "detected_intent": "UNKNOWN",
        "raw_extracted_entity": None,
        "normalized_entity": None,
        "entity_type": None,
        "normalization_rule_used": None,
        "selected_primary_object": None,
        "selected_business_key": None,
        "extracted_entities": "[]",
        "evidence": "[]",
        "sql_queries": "[]",
        "report_path": "",
        "report_snapshot": "",
        "verification_checks": "[]",
        "ai_debug_trace": "",
    }


def _terminal_ai_trace(investigation_metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a truthful, machine-readable AI trace for every persisted result."""
    raw_trace = investigation_metadata.get("ai_debug_trace")
    if isinstance(raw_trace, dict):
        trace = dict(raw_trace)
    else:
        try:
            parsed = json.loads(raw_trace) if raw_trace else {}
            trace = dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, json.JSONDecodeError):
            trace = {}

    provenance = str(investigation_metadata.get("answer_provenance") or "")
    detected_intent = str(investigation_metadata.get("detected_intent") or "")
    if provenance == "AI_SKIPPED_BY_EVIDENCE_GATE":
        trace.setdefault("ai_reasoning_invoked", False)
        trace.setdefault("ai_skip_reason", "evidence_gate_not_reproduced")
        trace.setdefault("ai_outcome", "evidence_gate")
    elif provenance == "AI_INVOCATION_FAILED":
        trace.setdefault("ai_reasoning_invoked", True)
        trace.setdefault("ai_outcome", "provider_failure")
    elif provenance == "AI_ANSWERED":
        trace.setdefault("ai_reasoning_invoked", True)
        trace.setdefault("ai_outcome", "success")
    elif detected_intent.startswith("INSUFFICIENT_DATABASE_EVIDENCE:"):
        reason = detected_intent.split(":", 1)[1].strip().lower()
        trace.setdefault("ai_reasoning_invoked", False)
        trace.setdefault("ai_skip_reason", reason or "insufficient_database_evidence")
        trace.setdefault("ai_outcome", "insufficient_evidence")
    else:
        trace.setdefault("ai_reasoning_invoked", False)
        trace.setdefault("ai_skip_reason", "application_terminal_path_before_ai")
        trace.setdefault("ai_outcome", "other")

    # Persist transfer normalization and target-selection trace in an existing DB JSON column.
    # Keep output compact by omitting absent values, which also preserves historical exact-trace tests.
    trace_fields = (
        "raw_extracted_entity",
        "normalized_entity",
        "entity_type",
        "normalization_rule_used",
        "selected_primary_object",
        "selected_business_key",
        "evidence_gate_reason",
    )
    for key in trace_fields:
        value = investigation_metadata.get(key)
        if value is not None:
            trace.setdefault(key, value)
    return trace


def _approved_knowledge_context(db: Session, payload: ChatAskRequest) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for approved knowledge context within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    approved_matches = get_knowledge_retriever().retrieve(
        db,
        KnowledgeQuery(
            organization_id=payload.organization_id,
            workspace_id=payload.workspace_id,
            question=payload.question,
            top_k=3,
            metadata_filters={"source": "approved_knowledge", "approval_status": "approved"},
        ),
    )
    if not approved_matches:
        return ""
    return (
        "## Similar Approved Issue\n"
        + "\n\n".join(
            "Similar approved issue found\n"
            f"Reference article: {item.title}\n"
            f"Previous evidence: {item.snippet[:700]}\n"
            f"Confidence: {int((item.metadata.get('confidence') or item.score or 0) * 100)}%"
            for item in approved_matches
        )
        + "\n\n"
    )


def _tokens(value: str) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for tokens within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return {token.strip(".,:;()[]{}").lower() for token in value.split() if len(token.strip(".,:;()[]{}")) >= 3}


def _format_retrieved_items(items, *, empty: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for format retrieved items within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if not items:
        return f"- {empty}"
    return "\n".join(
        f"- {item.title} ({item.source}, score {int(item.score * 100)}%): {item.snippet[:240]}"
        for item in items
    )


def _previous_investigation_matches(db: Session, payload: ChatAskRequest, *, limit: int = 5) -> list[InvestigationModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for previous investigation matches within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    question_tokens = _tokens(payload.question)
    candidates = (
        db.query(InvestigationModel)
        .filter(
            InvestigationModel.organization_id == payload.organization_id,
            InvestigationModel.workspace_id == payload.workspace_id,
        )
        .order_by(InvestigationModel.created_at.desc())
        .limit(50)
        .all()
    )
    scored: list[tuple[float, InvestigationModel]] = []
    for item in candidates:
        haystack = _tokens(f"{item.user_question} {item.detected_intent} {item.ai_answer[:1000]}")
        score = len(question_tokens & haystack) / max(1, len(question_tokens))
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
    return [item for _, item in scored[:limit]]


def _workspace_name(db: Session, workspace_id: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for workspace name within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    workspace = db.get(WorkspaceModel, workspace_id)
    return workspace.name if workspace else workspace_id


def _generate_lightweight_report(
    *,
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
    title: str,
    mode: str,
    database_name: str,
    confidence: float,
    summary: str,
    sections: list[ReportSection],
) -> tuple[dict[str, str], str, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for generate lightweight report within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    report = InvestigationReport(
        cover=ReportCover(
            title="Enterprise Investigation Report",
            workspace=_workspace_name(db, payload.workspace_id),
            database=database_name,
            generated_by=generated_by,
            generated_on=now_label(),
            investigation_id=new_investigation_id(),
            report_version=REPORT_VERSION,
        ),
        executive_summary=ExecutiveSummary(
            issue_title=title[:96],
            issue_description=payload.question,
            severity="Informational" if mode != InvestigationMode.INVESTIGATION.value else "Medium",
            business_impact="No production impact was inferred unless supported by collected evidence.",
            confidence_score=int(confidence * 100),
            estimated_root_cause="Not generated for this mode." if mode != InvestigationMode.INVESTIGATION.value else summary,
            recommendation_summary=summary,
            status=f"{mode} Complete",
        ),
        sections=[
            ReportSection(
                title="Stage 1 - Understand the Question",
                items=[
                    f"Investigation Mode: {mode}",
                    f"User Question: {payload.question}",
                    f"Confidence: {int(confidence * 100)}%",
                ],
            ),
            *sections,
        ],
    )
    generated = generate_investigation_report_files(report)
    return generated.links(), report.cover.investigation_id, str(generated.directory)


def _run_knowledge_search(
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
    intent,
    entities,
    mode: ModeClassification,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for run knowledge search within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    retriever = get_knowledge_retriever()
    semantic_matches = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=payload.organization_id,
            workspace_id=payload.workspace_id,
            question=payload.question,
            top_k=8,
        ),
    )
    approved_matches = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=payload.organization_id,
            workspace_id=payload.workspace_id,
            question=payload.question,
            top_k=5,
            metadata_filters={"source": "approved_knowledge", "approval_status": "approved"},
        ),
    )
    previous = _previous_investigation_matches(db, payload)
    previous_text = "\n".join(
        f"- {item.user_question[:140]} (intent {item.detected_intent}, confidence {int((item.confidence_score or 0) * 100)}%)"
        for item in previous
    ) or "- No similar previous investigations found in this workspace."
    top_score = max([item.score for item in [*semantic_matches, *approved_matches]] or [0.0])
    confidence = min(0.88, max(0.3, top_score))
    sources = list(dict.fromkeys([item.title for item in [*approved_matches, *semantic_matches]] + ["previous investigations"]))
    answer = (
        "Knowledge Search Complete.\n\n"
        "No live SQL was executed because this was classified as a knowledge-search question.\n\n"
        "## Stage 1 - Understand the Question\n"
        f"- Investigation Mode: {mode.mode.value}\n"
        f"- Mode Rationale: {mode.rationale}\n"
        f"- Detected Intent: {intent.intent.value}\n"
        f"- Required Stages: {', '.join(mode.required_stages)}\n\n"
        "## Sources Searched\n"
        "- Previous investigations\n"
        "- Approved knowledge articles\n"
        "- Uploaded documents through semantic retrieval\n\n"
        "## Similar Approved Knowledge\n"
        f"{_format_retrieved_items(approved_matches, empty='No approved knowledge article matched strongly.')}\n\n"
        "## Similar Uploaded Document Evidence\n"
        f"{_format_retrieved_items(semantic_matches, empty='No uploaded document chunk matched strongly.')}\n\n"
        "## Previous Investigation Matches\n"
        f"{previous_text}\n\n"
        "## Reusable Fix Guidance\n"
        "Use only approved knowledge as reusable fix guidance. Uploaded documents and previous AI answers are reference evidence until a human approves them.\n\n"
        "## Differences To Check\n"
        "- Confirm the connected workspace and database match the current issue.\n"
        "- Compare object names, status values, stored procedures, and business keys before reusing a fix.\n"
        "- If this is an active production failure, ask an investigation question so the app can collect live SQL evidence.\n\n"
        f"Confidence: {int(confidence * 100)}%"
    )
    report_links, investigation_id, report_path = _generate_lightweight_report(
        db=db,
        payload=payload,
        generated_by=generated_by,
        title=f"Knowledge Search - {payload.question}",
        mode=mode.mode.value,
        database_name="Knowledge layer only",
        confidence=confidence,
        summary="Knowledge search completed without live SQL. Use approved knowledge as reusable guidance.",
        sections=[
            ReportSection(title="Sources Searched", items=["Previous investigations", "Approved knowledge articles", "Uploaded documents"]),
            ReportSection(
                title="Approved Knowledge Matches",
                tables=[
                    ReportTable(
                        title="Approved Knowledge",
                        columns=["Title", "Source", "Score", "Snippet"],
                        rows=[
                            {"Title": item.title, "Source": item.source, "Score": item.score, "Snippet": item.snippet[:500]}
                            for item in approved_matches
                        ]
                        or [{"Title": "None", "Source": "", "Score": "", "Snippet": "No approved knowledge article matched strongly."}],
                    )
                ],
            ),
            ReportSection(
                title="Semantic Matches",
                tables=[
                    ReportTable(
                        title="Retrieved Evidence",
                        columns=["Title", "Source", "Score", "Snippet"],
                        rows=[
                            {"Title": item.title, "Source": item.source, "Score": item.score, "Snippet": item.snippet[:500]}
                            for item in semantic_matches
                        ]
                        or [{"Title": "None", "Source": "", "Score": "", "Snippet": "No uploaded document chunk matched strongly."}],
                    )
                ],
            ),
            ReportSection(
                title="Previous Investigation Matches",
                tables=[
                    ReportTable(
                        title="Previous Investigations",
                        columns=["Question", "Intent", "Confidence"],
                        rows=[
                            {
                                "Question": item.user_question[:300],
                                "Intent": item.detected_intent,
                                "Confidence": int((item.confidence_score or 0) * 100),
                            }
                            for item in previous
                        ]
                        or [{"Question": "No similar previous investigations found.", "Intent": "", "Confidence": ""}],
                    )
                ],
            ),
        ],
    )
    metadata = _empty_investigation_metadata()
    metadata["investigation_id"] = investigation_id
    metadata["detected_intent"] = f"{mode.mode.value}:{intent.intent.value}"
    metadata["extracted_entities"] = json.dumps(
        [{"entity_type": entity.entity_type, "value": entity.value} for entity in entities.entities],
        default=str,
    )
    metadata["evidence"] = json.dumps(
        [{"title": item.title, "source": item.source, "score": item.score} for item in semantic_matches],
        default=str,
    )
    metadata["report_path"] = report_path
    return answer, sources, confidence, report_links, metadata


def _target_object_not_found(question: str, metadata, intent=None) -> tuple[bool, str, list[str]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for target object not found within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if intent and intent.intent == InvestigationIntent.STORED_PROCEDURE_ANALYSIS:
        return False, "", []
    if intent and intent.intent in {InvestigationIntent.HEALTH_ASSESSMENT, InvestigationIntent.GENERAL_DATABASE_QUESTION}:
        return False, "", []
    problem = parse_problem_phrase(question)
    if not problem.issue_kind or not problem.target_terms:
        return False, "", []
    target = resolve_table_from_terms(problem.target_terms, metadata)
    if target is not None:
        return False, target.name, problem.target_terms
    if problem.issue_kind == "duplicate":
        for table in metadata.tables:
            name = table.name.lower()
            if any(term.rstrip("s") in name or term in name for term in problem.target_terms):
                return False, table.name, problem.target_terms
    return True, " ".join(problem.target_terms), problem.target_terms


def _object_not_found_answer(
    *,
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
    mode: ModeClassification,
    intent,
    missing_target: str,
    context,
    database_name: str,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for object not found answer within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    searched = [
        "database tables",
        "database views",
        "stored procedures",
        "uploaded documents",
        "approved knowledge",
    ]
    semantic_matches = context.documents[:6]
    confidence = 0.25 if not semantic_matches else min(0.45, max(item.score for item in semantic_matches))
    answer = (
        "Insufficient Database Evidence.\n\n"
        "The app stopped before generating root-cause hypotheses because the requested business term could not be resolved to connected database evidence.\n\n"
        "## Stage 1 - Understand the Question\n"
        f"- Investigation Mode: {mode.mode.value}\n"
        f"- Detected Intent: {intent.intent.value}\n"
        f"- Requested Business Term: {missing_target}\n\n"
        "## Searched Metadata\n"
        + "\n".join(f"- {item}" for item in searched)
        + "\n\n## Closest Matching Objects\n"
        + "\n".join(f"- {table.name}" for table in context.metadata.tables[:5])
        + "\n\n## Semantic Matches\n"
        f"{_format_retrieved_items(semantic_matches, empty='No semantic document matches found.')}\n\n"
        "## Confidence\n"
        f"- {int(confidence * 100)}%\n"
        "- Confidence is low because the requested term could not be resolved from connected schema evidence.\n\n"
        "## Why RCA Was Not Generated\n"
        "- No safe RCA was generated because the affected object could not be mapped to a table, view, procedure, or approved document.\n\n"
        "## Evidence Needed Next\n"
        "- Confirm that this workspace is connected to the correct customer database.\n"
        "- Check whether the object uses a different name in this database.\n"
        "- Upload or approve business process documents that map business terms to physical table/procedure names.\n"
        "- Ask again after the correct database or object mapping is available."
    )
    report_links, investigation_id, report_path = _generate_lightweight_report(
        db=db,
        payload=payload,
        generated_by=generated_by,
        title=f"Insufficient Database Evidence - {payload.question}",
        mode=mode.mode.value,
        database_name=database_name,
        confidence=confidence,
        summary="Reported issue could not be investigated because the requested business term was not found in connected database evidence.",
        sections=[
            ReportSection(
                title="Insufficient Database Evidence",
                items=[
                    f"Requested Business Term: {missing_target}",
                    "Root-cause hypotheses were not generated.",
                    "Live SQL evidence queries were not planned for an unresolved target object.",
                ],
            ),
            ReportSection(title="Searched Metadata", items=searched),
            ReportSection(title="Closest Matching Objects", items=[table.name for table in context.metadata.tables[:5]] or ["No table metadata was available."]),
            ReportSection(
                title="Semantic Matches",
                tables=[
                    ReportTable(
                        title="Retrieved Evidence",
                        columns=["Title", "Source", "Score", "Snippet"],
                        rows=[
                            {"Title": item.title, "Source": item.source, "Score": item.score, "Snippet": item.snippet[:500]}
                            for item in semantic_matches
                        ]
                        or [{"Title": "None", "Source": "", "Score": "", "Snippet": "No semantic document matches found."}],
                    )
                ],
            ),
            ReportSection(
                title="Evidence Needed Next",
                items=[
                    "Confirm that this workspace is connected to the correct customer database.",
                    "Check whether the object uses a different physical table/procedure name.",
                    "Upload or approve business process documents that map business terms to database objects.",
                ],
            ),
        ],
    )
    metadata = _empty_investigation_metadata()
    metadata["investigation_id"] = investigation_id
    metadata["detected_intent"] = f"INSUFFICIENT_DATABASE_EVIDENCE:{intent.intent.value}"
    metadata["evidence"] = json.dumps(
        {
            "missing_target": missing_target,
            "searched_sources": searched,
            "semantic_matches": [{"title": item.title, "score": item.score} for item in semantic_matches],
        },
        default=str,
    )
    metadata["report_path"] = report_path
    return answer, [*searched, *(item.title for item in semantic_matches)], confidence, report_links, metadata


def _run_business_rule_discovery(
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
    intent,
    entities,
    mode: ModeClassification,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for run business rule discovery within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    retriever = get_knowledge_retriever()
    documents = retriever.retrieve(
        db,
        KnowledgeQuery(
            organization_id=payload.organization_id,
            workspace_id=payload.workspace_id,
            question=payload.question,
            top_k=8,
        ),
    )
    connection = _find_workspace_connection(db, payload)
    metadata_lines = ["- No active database connection; schema, view, constraint, and procedure discovery were skipped."]
    procedure_lines = ["- No stored procedures analyzed."]
    sources = [item.title for item in documents]
    confidence = max([item.score for item in documents] or [0.35])
    if connection is not None:
        try:
            connector = get_connection_pool().get_or_create(
                connection.id,
                DatabaseEngine(connection.engine),
                _build_connection_string(connection),
            )
            connector.connect()
            context = discover_context(
                connector,
                db,
                payload.organization_id,
                payload.workspace_id,
                payload.question,
                entities,
            )
            ranking = rank_relevant_objects(
                question=payload.question,
                intent=intent,
                entities=entities,
                metadata=context.metadata,
            )
            procedure_analysis = analyze_stored_procedures(connector, ranking.metadata.procedures)
            metadata_lines = [
                f"- Table: {table.name}; columns: {', '.join(table.columns[:10])}; foreign keys: {len(table.foreign_keys or [])}; indexes: {len(table.indexes or [])}"
                for table in ranking.metadata.tables[:8]
            ] or ["- No matching tables found."]
            metadata_lines.extend(f"- View: {view}" for view in ranking.metadata.views[:8])
            procedure_lines = [
                f"- {proc.name}: reads {', '.join(proc.tables_read) or 'none confirmed'}; writes {', '.join(proc.tables_written) or 'none confirmed'}; rules: {', '.join(proc.business_rules[:4]) or 'no explicit rule text extracted'}"
                for proc in procedure_analysis[:8]
            ] or ["- No matching stored procedures analyzed."]
            documents = context.documents or documents
            sources = [connection.name, "schema metadata", *(item.title for item in documents)]
            confidence = min(0.86, max(confidence, 0.55 if ranking.metadata.tables or ranking.metadata.procedures else 0.4))
        except (DatabaseConnectionError, ValueError) as exc:
            metadata_lines = [f"- Active database connection exists but failed: {exc}"]
            confidence = min(confidence, 0.45)
    answer = (
        "Business Rule Discovery Complete.\n\n"
        "No root-cause hypotheses were generated because this mode is for rule discovery, not incident diagnosis.\n\n"
        "## Stage 1 - Understand the Question\n"
        f"- Investigation Mode: {mode.mode.value}\n"
        f"- Mode Rationale: {mode.rationale}\n"
        f"- Detected Intent: {intent.intent.value}\n"
        f"- Required Stages: {', '.join(mode.required_stages)}\n\n"
        "## Knowledge And Documents\n"
        f"{_format_retrieved_items(documents, empty='No matching uploaded or approved knowledge found.')}\n\n"
        "## Schema, Views, And Constraints\n"
        + "\n".join(metadata_lines)
        + "\n\n## Stored Procedure Logic\n"
        + "\n".join(procedure_lines)
        + "\n\n## Recommendation\n"
        "- Use this output to document expected rules, statuses, constraints, and procedure guards.\n"
        "- Ask a live investigation question only when you need evidence-gated root-cause analysis for a specific failure.\n\n"
        f"Confidence: {int(confidence * 100)}%"
    )
    report_links, investigation_id, report_path = _generate_lightweight_report(
        db=db,
        payload=payload,
        generated_by=generated_by,
        title=f"Business Rule Discovery - {payload.question}",
        mode=mode.mode.value,
        database_name=connection.name if connection else "No active database connection",
        confidence=confidence,
        summary="Business rule discovery completed without root-cause hypotheses.",
        sections=[
            ReportSection(title="Mode Guardrail", items=["No root-cause hypotheses were generated.", "No fix was recommended without a reported live failure."]),
            ReportSection(
                title="Knowledge And Documents",
                tables=[
                    ReportTable(
                        title="Retrieved Evidence",
                        columns=["Title", "Source", "Score", "Snippet"],
                        rows=[
                            {"Title": item.title, "Source": item.source, "Score": item.score, "Snippet": item.snippet[:500]}
                            for item in documents
                        ]
                        or [{"Title": "None", "Source": "", "Score": "", "Snippet": "No matching uploaded or approved knowledge found."}],
                    )
                ],
            ),
            ReportSection(title="Schema, Views, And Constraints", items=metadata_lines),
            ReportSection(title="Stored Procedure Logic", items=procedure_lines),
        ],
    )
    investigation_metadata = _empty_investigation_metadata()
    investigation_metadata["investigation_id"] = investigation_id
    investigation_metadata["detected_intent"] = f"{mode.mode.value}:{intent.intent.value}"
    investigation_metadata["extracted_entities"] = json.dumps(
        [{"entity_type": entity.entity_type, "value": entity.value} for entity in entities.entities],
        default=str,
    )
    investigation_metadata["evidence"] = json.dumps(
        [{"title": item.title, "source": item.source, "score": item.score} for item in documents],
        default=str,
    )
    investigation_metadata["report_path"] = report_path
    return answer, list(dict.fromkeys(sources)), confidence, report_links, investigation_metadata


def _discovered_target_context(ranking, procedure_analysis) -> dict[str, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for discovered target context within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    target = next((item.name for item in ranking.objects if item.object_type == "table"), "")
    if not target and ranking.metadata.tables:
        target = ranking.metadata.tables[0].name
    target_l = target.lower()
    upstream: list[str] = []
    downstream: list[str] = []
    for table in ranking.metadata.tables:
        for fk in table.foreign_keys or []:
            referred = str(fk.get("referred_table") or "")
            if table.name.lower() == target_l and referred:
                upstream.append(referred)
            if referred.lower() == target_l:
                downstream.append(table.name)
    supporting = [
        item.name
        for item in ranking.objects
        if item.name != target and item.object_type in {"table", "view", "procedure"}
    ][:6]
    write_path = [
        proc.name
        for proc in procedure_analysis
        if target_l and any(table.lower() == target_l for table in proc.tables_written)
    ]
    read_path = [
        proc.name
        for proc in procedure_analysis
        if target_l and any(table.lower() == target_l for table in proc.tables_read)
    ]
    return {
        "target": target or "Not determined from available metadata",
        "supporting": ", ".join(dict.fromkeys(supporting)) or "None ranked",
        "upstream": ", ".join(dict.fromkeys(upstream)) or "None discovered",
        "downstream": ", ".join(dict.fromkeys(downstream)) or "None discovered",
        "write_path": ", ".join(dict.fromkeys(write_path)) or "No write path confirmed",
        "read_path": ", ".join(dict.fromkeys(read_path)) or "No procedure read path confirmed",
    }


def _self_validation_lines(*, target_context: dict[str, str], evidence, hypothesis_reasoning) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for self validation lines within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    inspected_target = any(target_context["target"] in item.purpose or target_context["target"] in item.sql for item in evidence)
    conclusions_have_evidence = any(item.supporting_evidence for item in hypothesis_reasoning.ranked_root_causes)
    unrelated_ignored = len(hypothesis_reasoning.ranked_root_causes) > 0
    alternatives = len(hypothesis_reasoning.ranked_root_causes) > 1
    return [
        f"Did I investigate the target object? {'Yes' if inspected_target else 'Needs more evidence'}",
        f"Did I collect evidence? {'Yes' if evidence else 'No'}",
        f"Does every conclusion have evidence? {'Yes' if conclusions_have_evidence else 'Needs more evidence'}",
        f"Did I ignore unrelated objects? {'Yes' if unrelated_ignored else 'Needs more evidence'}",
        f"Could another hypothesis explain this? {'Yes, alternatives are ranked below' if alternatives else 'No alternative was strongly evidenced'}",
    ]


def _ai_reasoning_status(*, llm_configured: bool, llm_used: bool) -> dict[str, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for ai reasoning status within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    settings = Settings.from_env()
    if llm_used:
        return {
            "ai_assisted_reasoning": "Enabled",
            "reason": "OpenAI LLM reasoning was applied after deterministic evidence collection.",
            "evidence_package_sent": "Yes",
            "llm_evidence_validation": "Passed",
            "evidence_citations": "Passed",
            "pii_masking": "Applied",
            "pii_masking_scope": "Names, emails, phone numbers, insurance/account identifiers were masked in the LLM evidence package.",
        }
    if not settings.openai_api_key:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "OPENAI_API_KEY not configured",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
            "pii_masking": "Ready",
            "pii_masking_scope": "Names, emails, phone numbers, insurance/account identifiers are masked before any LLM evidence package is sent.",
        }
    if not settings.ai_reasoning_enabled:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "AI_REASONING_ENABLED=false",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
            "pii_masking": "Ready",
            "pii_masking_scope": "Names, emails, phone numbers, insurance/account identifiers are masked before any LLM evidence package is sent.",
        }
    if not llm_configured:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "LLM provider is not configured for OpenAI evidence-grounded reasoning.",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
            "pii_masking": "Ready",
            "pii_masking_scope": "Names, emails, phone numbers, insurance/account identifiers are masked before any LLM evidence package is sent.",
        }
    return {
        "ai_assisted_reasoning": "Enabled",
        "reason": "OpenAI was configured, but deterministic output was kept because no usable evidence-cited AI reasoning was returned.",
        "evidence_package_sent": "Yes",
        "llm_evidence_validation": "Failed",
        "evidence_citations": "Failed",
        "pii_masking": "Applied",
        "pii_masking_scope": "Names, emails, phone numbers, insurance/account identifiers were masked in the LLM evidence package.",
    }


def _verification_sections_from_models(checks: list[VerificationCheckModel]) -> list[ReportSection]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verification sections from models within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    suggested_rows = [
        {
            "Claim to verify": item.claim,
            "Purpose": item.purpose,
            "Claim being verified": item.claim_being_verified,
            "Evidence logic": item.evidence_logic,
            "Generated read-only SQL": item.verification_sql,
            "Expected result": item.expected_result,
            "Expected result explanation": item.expected_result_explanation,
            "Interpretation": item.interpretation,
            "Conclusion template": item.conclusion_template,
            "Risk level": item.risk_level,
            "Source": item.source,
            "Status": item.status,
        }
        for item in checks
    ]
    executed_rows = [
        {
            "Claim": item.claim,
            "Purpose": item.purpose,
            "Evidence logic": item.evidence_logic,
            "SQL executed": item.verification_sql,
            "Expected result": item.expected_result,
            "Actual result summary": item.actual_result_summary,
            "Interpretation": item.interpretation,
            "Conclusion": item.conclusion_template,
            "Status": item.status,
            "Confidence impact": item.confidence_impact,
            "Timestamp": item.verified_at.isoformat() if item.verified_at else "",
            "Verified by": item.verified_by,
        }
        for item in checks
        if item.status not in {"Pending", "Skipped"}
    ]
    return [
        ReportSection(
            title="Suggested Verification Checks",
            paragraphs=[
                "These checks are suggestions only. A user must approve execution. The app validates every SQL statement before running it and allows only SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN."
            ],
            tables=[
                ReportTable(
                    title="Suggested Verification Checks",
                    columns=[
                        "Claim to verify",
                        "Purpose",
                        "Claim being verified",
                        "Evidence logic",
                        "Generated read-only SQL",
                        "Expected result",
                        "Expected result explanation",
                        "Interpretation",
                        "Conclusion template",
                        "Risk level",
                        "Source",
                        "Status",
                    ],
                    rows=suggested_rows,
                )
            ],
        ),
        ReportSection(
            title="Evidence Verification Results",
            paragraphs=[
                "Verification results were produced only after a user approved execution. No write SQL or stored procedure execution is allowed."
            ],
            tables=[
                ReportTable(
                    title="Evidence Verification Results",
                    columns=[
                        "Claim",
                        "Purpose",
                        "Evidence logic",
                        "SQL executed",
                        "Expected result",
                        "Actual result summary",
                        "Interpretation",
                        "Conclusion",
                        "Status",
                        "Confidence impact",
                        "Timestamp",
                        "Verified by",
                    ],
                    rows=executed_rows
                    or [
                        {
                            "Claim": "No checks have been executed yet",
                            "Purpose": "",
                            "Evidence logic": "",
                            "SQL executed": "",
                            "Expected result": "",
                            "Actual result summary": "",
                            "Interpretation": "",
                            "Conclusion": "",
                            "Status": "Pending",
                            "Confidence impact": "",
                            "Timestamp": "",
                            "Verified by": "",
                        }
                    ],
                )
            ],
        ),
    ]


def _regenerate_report_with_verification(db: Session, investigation: InvestigationModel) -> dict[str, str] | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for regenerate report with verification within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if not investigation.report_snapshot_json:
        return None
    report = report_from_dict(json.loads(investigation.report_snapshot_json))
    checks = list(
        db.query(VerificationCheckModel)
        .filter(VerificationCheckModel.investigation_id == investigation.id)
        .order_by(VerificationCheckModel.created_at.asc())
        .all()
    )
    verification_titles = {"Suggested Verification Checks", "Evidence Verification Results"}
    sections = [section for section in report.sections if section.title not in verification_titles]
    sections.extend(_verification_sections_from_models(checks))
    updated_report = replace(report, sections=sections)
    generated = generate_investigation_report_files(updated_report)
    investigation.report_snapshot_json = json.dumps(report_to_dict(updated_report), default=str)
    investigation.report_path = str(generated.directory)
    investigation.report_storage_json = json.dumps(report_storage_references(generated), default=str)
    return generated.links()


def _metadata_with_active_diagnostics(
    ranked_metadata: MetadataSearchResult,
    active_metadata: MetadataSearchResult,
    *,
    limit: int = 12,
) -> MetadataSearchResult:
    """Retain active-schema diagnostic tables for correlation evidence planning."""
    ranked_names = {table.name.casefold() for table in ranked_metadata.tables}
    diagnostics = [
        table
        for table in active_metadata.tables
        if is_diagnostic_object(table.name) and table.name.casefold() not in ranked_names
    ]
    return replace(
        ranked_metadata,
        tables=[*ranked_metadata.tables[:8], *diagnostics][:limit],
    )


def _run_dynamic_investigation(
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for run dynamic investigation within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    intent = detect_intent(payload.question)
    entities = extract_entities(payload.question)
    mode = classify_investigation_mode(payload.question, intent)
    if intent.intent == InvestigationIntent.METADATA_VALIDATION:
        return _run_metadata_validation(db, payload, intent)
    if mode.mode == InvestigationMode.KNOWLEDGE_SEARCH:
        return _run_knowledge_search(db, payload, generated_by, intent, entities, mode)
    if mode.mode == InvestigationMode.BUSINESS_RULE_DISCOVERY:
        return _run_business_rule_discovery(db, payload, generated_by, intent, entities, mode)

    approved_context = _approved_knowledge_context(db, payload)
    connection = _find_workspace_connection(db, payload)
    if connection is None:
        return (
            f"{approved_context}"
            "I could not investigate the live database because this workspace has no active "
            "database connection. Add or test a database connection first, then ask again.",
            [],
            0.35,
            None,
            _empty_investigation_metadata(),
        )
    try:
        connection_string = _build_connection_string(connection)
        engine = DatabaseEngine(connection.engine)
        pool = get_connection_pool()
        connector_cache_key = pool.connector_cache_key(engine, connection_string)
        connector = get_connection_pool().get_or_create(
            connection.id,
            engine,
            connection_string,
        )
        connector.connect()
        metadata_context = _metadata_context_for_connection(
            payload,
            connection,
            connection_string,
            connector_cache_key=connector_cache_key,
        )
        active_schema_metadata, metadata_context = _load_and_validate_active_schema(connector, metadata_context, engine)
    except (DatabaseConnectionError, ValueError) as exc:
        return (
            "I could not investigate the live database because the saved connection failed: "
            f"{exc}",
            [connection.name],
            0.25,
            None,
            _empty_investigation_metadata(),
        )

    context = discover_context(
        connector,
        db,
        payload.organization_id,
        payload.workspace_id,
        payload.question,
        entities,
        metadata_context=metadata_context,
        schema_metadata=active_schema_metadata,
    )
    if context.metadata.target_object_not_found:
        return _target_object_not_found_metadata_answer(
            payload=payload,
            connection=connection,
            metadata=context.metadata,
            metadata_context=metadata_context,
            active_schema_metadata=active_schema_metadata,
        )
    resolution_metadata = resolution_metadata_for_schema(
        connector, context.metadata, active_schema_metadata.tables
    )
    entity_resolution = resolve_entities(connector, resolution_metadata, entities)
    if entity_resolution.resolutions and not entity_resolution.can_continue:
        return _entity_resolution_blocked_answer(connection.name, entities, entity_resolution)
    entities = _apply_entity_resolutions(entities, entity_resolution)
    entities, transfer_normalization_trace = normalize_transfer_entities(entities)
    context = replace(
        context,
        metadata=metadata_with_resolved_tables(
            context.metadata, resolution_metadata, entity_resolution
        ),
    )
    target_missing, missing_target, _ = _target_object_not_found(payload.question, context.metadata, intent)
    if target_missing and not entity_resolution.can_continue:
        return _object_not_found_answer(
            db=db,
            payload=payload,
            generated_by=generated_by,
            mode=mode,
            intent=intent,
            missing_target=missing_target,
            context=context,
            database_name=f"{connection.name} ({connection.engine})",
        )
    ranking = rank_relevant_objects(
        question=payload.question,
        intent=intent,
        entities=entities,
        metadata=context.metadata,
    )
    ranked_metadata = metadata_with_resolved_tables(
        ranking.metadata, resolution_metadata, entity_resolution
    )
    ranking = replace(
        ranking,
        metadata=_metadata_with_active_diagnostics(ranked_metadata, resolution_metadata),
    )
    relevance_terms = query_relevance_terms(payload.question, entities)
    definition_procedures = _definition_relevant_procedures(
        connector, active_schema_metadata.procedures, relevance_terms
    )
    ranking = replace(
        ranking,
        metadata=replace(ranking.metadata, procedures=definition_procedures[:20]),
    )
    business_identifiers = [
        entity.value for entity in entities.entities
        if entity.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    ]
    relevant_objects_examined = bool(ranking.metadata.tables or ranking.metadata.views or definition_procedures)
    if business_identifiers and not relevant_objects_examined:
        metadata = _empty_investigation_metadata()
        metadata["detected_intent"] = "INSUFFICIENT_DATABASE_EVIDENCE:RELEVANT_SCHEMA_OBJECTS_NOT_DISCOVERED"
        metadata["extracted_entities"] = json.dumps(
            [{"entity_type": entity.entity_type, "value": entity.value} for entity in entities.entities]
        )
        return (
            "INSUFFICIENT_DATABASE_EVIDENCE:RELEVANT_SCHEMA_OBJECTS_NOT_DISCOVERED",
            [connection.name],
            0.0,
            None,
            metadata,
        )
    procedure_analysis = analyze_stored_procedures(connector, ranking.metadata.procedures)
    planning_warning = ""
    try:
        plan = build_investigation_plan(intent.intent, ranking.metadata, entities)
    except Exception as exc:
        plan = []
        planning_warning = f"Evidence SQL planning was skipped because generated SQL did not pass safety validation: {exc}"
    evidence = execute_evidence_plan(connector, plan)
    for index, procedure in enumerate(procedure_analysis, start=1):
        if not procedure.definition_available:
            continue
        evidence.append(
            EvidenceResult(
                purpose=f"Inspect calculation logic in {procedure.name}",
                sql="",
                rows=[{
                    "procedure_name": procedure.name,
                    "definition_excerpt": procedure.definition_excerpt,
                    "business_rules": procedure.business_rules,
                    "tables_read": procedure.tables_read,
                }],
                evidence_id=f"PROC-{index}",
            )
        )
    evidence.extend(_expand_related_id_evidence(connector, ranking.metadata, evidence))
    correlated_evidence = correlate_evidence(
        evidence=evidence,
        procedure_analysis=procedure_analysis,
        documents=context.documents,
    )
    evidence_focus = build_evidence_focus(
        question=payload.question,
        intent=intent.intent,
        entities=entities,
        metadata=ranking.metadata,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=context.documents,
    )
    evidence_gate = run_evidence_gate(
        question=payload.question,
        intent=intent.intent,
        entities=entities,
        metadata=ranking.metadata,
        evidence=evidence,
        evidence_focus=evidence_focus,
        documents=context.documents,
    )
    hypothesis_reasoning = run_hypothesis_investigation(
        question=payload.question,
        intent=intent,
        entities=entities,
        ranked_objects=ranking.objects,
        metadata=ranking.metadata,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=context.documents,
        evidence_focus=evidence_focus,
    )
    if evidence_gate.required and not evidence_gate.reproduced:
        reasoning = unreproduced_reasoning(evidence_gate)
        llm_configured = llm_reasoning_enabled()
        llm_used = False
        settings = Settings.from_env()
        ai_debug_trace = {
            "ai_reasoning_invoked": False,
            "ai_skip_reason": "evidence_gate_not_reproduced",
            "ai_outcome": "evidence_gate",
            "ai_skip_branch": "evidence_gate.required_and_not_reproduced",
            "llm_model_name": settings.llm_model,
            "prompt_version": AI_REASONING_PROMPT_VERSION,
            "input_tokens": 0,
            "output_tokens": 0,
        } if settings.ai_debug_trace_enabled else None
    else:
        reasoning = reason_about_evidence(
            payload.question,
            intent,
            entities,
            ranking.metadata,
            evidence,
            context.documents,
            correlated_evidence,
            procedure_analysis,
            evidence_focus,
        )
        settings = Settings.from_env()
        llm_configured = llm_reasoning_enabled(settings)
        ai_debug_trace = {} if settings.ai_debug_trace_enabled else None
        enhanced_reasoning = enhance_reasoning_with_llm(
            question=payload.question,
            intent=intent,
            deterministic_reasoning=reasoning,
            evidence=evidence,
            correlated_evidence=correlated_evidence,
            procedure_analysis=procedure_analysis,
            documents=context.documents,
            evidence_focus=evidence_focus,
            settings=settings,
            debug_trace=ai_debug_trace,
        )
        llm_used = enhanced_reasoning is not reasoning
        reasoning = enhanced_reasoning
    if ai_debug_trace is not None:
        ai_debug_trace.update({
            "metadata_cache": getattr(active_schema_metadata, "cache_diagnostics", {}),
            "raw_metadata_objects": {
                "tables": active_schema_metadata.tables,
                "views": active_schema_metadata.views,
                "procedures": active_schema_metadata.procedures,
            },
            "metadata_candidates": ranking.metadata.candidate_trace,
            "entity_resolution": [asdict(item) for item in entity_resolution.resolutions],
            "transfer_identifier_normalization": asdict(transfer_normalization_trace),
            "extracted_business_entities": [
                asdict(item) for item in extract_entities(payload.question).entities
                if item.entity_type in {"business_key", "business_identifier", "exact_id_or_code"}
            ],
            "ranked_objects": [asdict(item) for item in ranking.objects],
            "sql_plan": [asdict(item) for item in plan],
            "sql_evidence": [
                {"evidence_id": item.evidence_id, "purpose": item.purpose, "sql": item.sql, "row_count": len(item.rows), "error": item.error}
                for item in evidence
            ],
            "evidence_gate": asdict(evidence_gate),
        })
    recommendation = recommend_actions(
        intent=intent.intent,
        reasoning=reasoning,
        correlated_evidence=correlated_evidence,
    )
    confidence = score_confidence(ranking.metadata, evidence, context.documents, evidence_focus)
    confidence_notes = confidence_factors(ranking.metadata, evidence, context.documents, evidence_focus)
    if planning_warning:
        confidence = min(confidence, 0.35)
        confidence_notes.append(f"- {planning_warning}")
    if evidence_gate.required and not evidence_gate.reproduced:
        confidence = min(confidence, 0.35)
        confidence_notes.extend(f"- Evidence gate blocked root-cause analysis: {item}" for item in evidence_gate.blocking_reasons)
    verification_checks = []
    if Settings.from_env().verification_agent_enabled:
        try:
            verification_checks = suggest_verification_checks(
                question=payload.question,
                intent=intent.intent,
                metadata=ranking.metadata,
                evidence=evidence,
                evidence_focus=evidence_focus,
                evidence_gate=evidence_gate,
                procedure_analysis=procedure_analysis,
                documents=context.documents,
                reasoning=reasoning,
            )
        except Exception as exc:
            verification_checks = []
            confidence_notes.append(
                f"- Verification check suggestions were skipped because generated check SQL did not pass safety validation: {exc}"
            )
    ai_status = _ai_reasoning_status(llm_configured=llm_configured, llm_used=llm_used)
    bundle = DynamicInvestigationBundle(
        question=payload.question,
        intent=intent,
        entities=entities.entities,
        ranked_objects=ranking.objects,
        metadata=ranking.metadata,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        hypothesis_reasoning=hypothesis_reasoning,
        documents=context.documents,
        reasoning=reasoning,
        recommendation=recommendation,
        confidence=confidence,
        evidence_focus=evidence_focus,
        evidence_gate=evidence_gate,
        confidence_factors=confidence_notes,
        investigation_mode=mode.mode.value,
        mode_rationale=mode.rationale,
        ai_reasoning_status=ai_status,
        ai_debug_trace=ai_debug_trace,
        verification_checks=verification_checks,
        verification_results=[],
    )
    workspace = db.get(WorkspaceModel, payload.workspace_id)
    report = compose_report(
        bundle=bundle,
        workspace_name=workspace.name if workspace else payload.workspace_id,
        database_name=f"{connection.name} ({connection.engine}) [connection_id={connection.id}]",
        generated_by=generated_by,
    )
    generated_report = generate_investigation_report_files(report)
    entity_text = ", ".join(f"{entity.entity_type}={entity.value}" for entity in entities.entities) or "none"
    source_names = [connection.name, "schema metadata"]
    source_names.extend(table.name for table in ranking.metadata.tables[:5])
    source_names.extend(document.title for document in context.documents[:5])
    target_context = _discovered_target_context(ranking, procedure_analysis)
    self_validation = evidence_focus.self_validation or _self_validation_lines(
        target_context=target_context,
        evidence=evidence,
        hypothesis_reasoning=hypothesis_reasoning,
    )
    ranked_text = "\n".join(f"- {item.object_type}: {item.name} ({item.score}) - {item.reason}" for item in ranking.objects[:8]) or "- No ranked objects"
    correlated_text = "\n".join(f"- {item.evidence_type} {item.subject}: {item.finding}" for item in correlated_evidence[:8]) or "- No correlated evidence"
    selected_candidates = [
        item for item in ranking.metadata.candidate_trace if item.get("decision") == "selected"
    ][:10]
    rejected_candidates = [
        item for item in ranking.metadata.candidate_trace if item.get("decision") == "rejected"
    ][:10]
    metadata_debug_text = "\n".join(
        [
            f"- workspace_id: {payload.workspace_id}",
            f"- connection_id: {connection.id}",
            f"- database_name: {metadata_context.database_name}",
            f"- schema_name: {metadata_context.schema_name or 'default'}",
            f"- database_engine: {ranking.metadata.engine_type or connection.engine}",
            f"- connection_string_database: {metadata_context.connection_string_database or 'unknown'}",
            f"- metadata_cache_key: {ranking.metadata.metadata_cache_key or metadata_context.cache_key}",
            f"- Discovered tables: {', '.join(active_schema_metadata.tables[:30]) or 'None'}",
            f"- Discovered procedures: {', '.join(active_schema_metadata.procedures[:30]) or 'None'}",
            "- Selected candidates: "
            + (
                "; ".join(f"{item.get('object_type')}:{item.get('name')} ({item.get('reason')})" for item in selected_candidates)
                or "None"
            ),
            "- Rejected candidates: "
            + (
                "; ".join(f"{item.get('object_type')}:{item.get('name')} ({item.get('reason')})" for item in rejected_candidates)
                or "None"
            ),
        ]
    )
    gate_text = "\n".join(
        [
            f"- Gate Required: {'Yes' if evidence_gate.required else 'No'}",
            f"- Issue Reproduced: {'Yes' if evidence_gate.reproduced else 'No'}",
            f"- Business Key Exists: {'Yes' if evidence_gate.business_key_exists else 'No'}",
            f"- Reported Condition Exists: {'Yes' if evidence_gate.reported_condition_exists else 'No'}",
            f"- Affected Rows Exist: {'Yes' if evidence_gate.affected_rows_exist else 'No'}",
            f"- Parent/Child Relationship Exists: {'Yes' if evidence_gate.parent_child_relationship_exists else 'No'}",
            *[f"- {item}" for item in evidence_gate.status_interpretation],
            *[f"- Blocked: {item}" for item in evidence_gate.blocking_reasons],
        ]
    )
    final_root_cause_text = "\n".join(f"- {item}" for item in reasoning.likely_root_causes) or "- No root cause generated."
    confidence_text = "\n".join(f"- {item}" for item in confidence_notes)
    verification_text = "\n".join(
        f"- Pending: {item.claim} | Source: {item.source} | Risk: {item.risk_level} | Expected: {item.expected_result}"
        for item in verification_checks
    ) or "- Verification suggestions disabled."
    missing_related_rows = next((item.rows for item in evidence if item.purpose == "Confirmed Missing Related Record Candidates"), [])
    missing_related_conclusion = ""
    if missing_related_rows:
        issue_types = sorted({str(row.get("issue_type") or "") for row in missing_related_rows if row.get("issue_type")})
        issue_summary = ", ".join(issue_types) or "missing related records"
        missing_related_conclusion = (
            "## Business Conclusion\n"
            "Read-only evidence found parent rows missing expected related child rows through discovered metadata relationships. "
            f"Observed issue type(s): {issue_summary}. Confirm the exact procedure, job, or status guard that should create the child row before applying a fix.\n\n"
        )
    hypothesis_text = "\n".join(
        f"- {item.hypothesis_id}: {item.description} ({int(item.initial_confidence * 100)}% initial)"
        for item in hypothesis_reasoning.hypotheses
    )
    hypothesis_rank_text = "\n".join(
        f"- Rank {index}: {item.hypothesis_id} {int(item.confidence * 100)}% - {item.description}; {item.reason}"
        for index, item in enumerate(hypothesis_reasoning.ranked_root_causes, start=1)
    )
    event_chain_text = "\n".join(f"- {item}" for item in hypothesis_reasoning.event_chain)
    answer = (
        "Investigation Complete.\n\n"
        f"Investigation ID: {report.cover.investigation_id}\n"
        f"Investigation Mode: {mode.mode.value}\n"
        f"Detected Intent: {intent.intent.value}\n"
        f"Response Type: {reasoning.response_type}\n"
        f"Extracted Entities: {entity_text}\n"
        f"AI-assisted reasoning: {ai_status['ai_assisted_reasoning']}\n"
        f"Reason: {ai_status['reason']}\n"
        f"Evidence package sent: {ai_status['evidence_package_sent']}\n"
        f"LLM evidence validation: {ai_status['llm_evidence_validation']}\n"
        f"Evidence citations: {ai_status['evidence_citations']}\n"
        "Professional report files have been generated for download.\n\n"
        f"{approved_context}"
        "## Stage 1 - Understand the Question\n"
        f"- Investigation Mode: {mode.mode.value}\n"
        f"- Mode Rationale: {mode.rationale}\n"
        f"- Investigation Goal: {intent.intent.value}\n"
        f"- User Goal: {hypothesis_reasoning.understanding.user_goal}\n"
        f"- Working Hypothesis: {hypothesis_reasoning.understanding.user_hypothesis}\n\n"
        "## Stage 2 - Discover Context\n"
        f"- Target Object: {evidence_focus.affected_object}\n"
        f"- Target Reason: {evidence_focus.affected_object_reason}\n"
        f"- Business Key: {evidence_focus.inferred_business_key or 'Not determined'} ({evidence_focus.business_key_reason})\n"
        f"- Supporting Objects: {target_context['supporting']}\n"
        f"- Upstream Objects: {target_context['upstream']}\n"
        f"- Downstream Objects: {target_context['downstream']}\n"
        f"- Write Path: {target_context['write_path']}\n"
        f"- Read Path: {target_context['read_path']}\n"
        f"- Documents Used: {', '.join(document.title for document in context.documents[:5]) or 'No matching uploaded documents found'}\n\n"
        "## Metadata Debug\n"
        f"{metadata_debug_text}\n\n"
        f"{missing_related_conclusion}"
        "## Stage 3 - Generate Investigation Hypotheses\n"
        f"{hypothesis_text}\n\n"
        "## Stage 4 - Plan Investigation\n"
        + "\n".join(
            f"- {item.purpose}: expected read-only evidence from generated SQL"
            for item in evidence[:8]
        )
        + "\n\n## Stage 5 - Collect Evidence\n"
        f"{correlated_text}\n\n"
        "## Evidence Gate\n"
        f"{gate_text}\n\n"
        "## Suggested Verification Checks\n"
        f"{verification_text}\n\n"
        "## Relevant Objects Investigated\n"
        f"{ranked_text}\n\n"
        "## Stage 6 - Reason\n"
        f"{reasoning.summary}\n\n"
        + (
            "## AI-assisted reasoning over collected evidence\n"
            "OpenAI reasoning was applied only after deterministic intent detection, metadata discovery, safe SQL validation, and evidence collection. The model did not connect to the database, execute SQL, or override SQL evidence.\n\n"
            if llm_used
            else (
                "AI reasoning note: deterministic reasoning only; the configured model did not return usable evidence-cited reasoning, so its output was not used.\n\n"
                if llm_configured
                else f"AI reasoning note: {ai_status['reason']}.\n\n"
            )
        )
        + "## Root Cause Analysis\n"
        f"{final_root_cause_text}\n\n"
        "## Diagnostic Hypotheses\n"
        f"{hypothesis_rank_text}\n\n"
        "## Confirmed Facts\n"
        + "\n".join(f"- {item}" for item in reasoning.confirmed_facts)
        + "\n\n## Inferred Findings\n"
        + "\n".join(f"- {item}" for item in reasoning.inferred_findings)
        + "\n\n## Hypotheses\n"
        + "\n".join(f"- {item}" for item in reasoning.hypotheses)
        + "\n\n## Write Path Ranking\n"
        + (
            "\n".join(
                f"- {item.procedure}: score={item.score}; writes affected object={item.writes_affected_object}; relationship={item.relationship_to_affected_object}; evidence={'; '.join(item.evidence_found)}"
                for item in evidence_focus.ranked_procedures[:8]
            )
            or "- No stored procedure write path was confirmed."
        )
        + "\n\n"
        "## Why It Happened\n"
        f"{event_chain_text}"
        + "\n\n## Supporting Evidence\n"
        + "\n".join(f"- {item}" for item in reasoning.supporting_evidence)
        + "\n\n## Recommended Next SQL\n"
        + "\n\n".join(_evidence_sql_block(item) for item in evidence[:5])
        + "\n\n## Recommendation\n"
        + "\n".join(
            [
                "- Immediate Fix: " + " ".join(recommendation.immediate_fix),
                "- Permanent Fix: " + " ".join(recommendation.permanent_fix),
                "- Monitoring: " + " ".join(recommendation.monitoring),
                f"- Risk: {recommendation.risk}",
            ]
        )
        + "\n\n## Self Validation\n"
        + "\n".join(f"- {item}" for item in self_validation)
        + "\n\n## Confidence Explanation\n"
        + f"- Overall confidence: {int(confidence * 100)}%\n"
        + confidence_text
        + "\n\n## Stage 7 - Dynamic Report\n"
        + "- The downloadable report was generated from the reasoning bundle after evidence collection and hypothesis ranking.\n"
        + "\n\n## Missing Information / Clarifying Questions\n"
        + "\n".join(f"- {item}" for item in reasoning.missing_evidence)
    )
    answer_provenance = (
        "AI_SKIPPED_BY_EVIDENCE_GATE"
        if evidence_gate.required and not evidence_gate.reproduced
        else "AI_ANSWERED"
        if llm_used
        else "AI_INVOCATION_FAILED"
        if ai_debug_trace and ai_debug_trace.get("ai_reasoning_invoked")
        else "AI_SKIPPED_BY_POLICY"
        if Settings.from_env().ai_reasoning_enabled
        else "DETERMINISTIC_ANSWERED"
    )
    relationship_proof = [
        item for item in evidence_gate.confirmed_facts
        if "relationship" in item.lower() or "parent-child" in item.lower()
    ]
    evidence_gate_reason = (
        "Issue reproduced from connected database evidence."
        if evidence_gate.reproduced
        else "; ".join(evidence_gate.blocking_reasons)
    )
    investigation_metadata = {
        "investigation_id": report.cover.investigation_id,
        "detected_intent": intent.intent.value,
        "raw_extracted_entity": transfer_normalization_trace.raw_extracted_entity,
        "normalized_entity": transfer_normalization_trace.normalized_entity,
        "entity_type": transfer_normalization_trace.entity_type,
        "normalization_rule_used": transfer_normalization_trace.normalization_rule_used,
        "selected_primary_object": evidence_focus.affected_object,
        "extracted_entities": json.dumps(
            [
                {
                    "entity_type": entity.entity_type,
                    "value": entity.value,
                }
                for entity in entities.entities
            ] + [
                {
                    "entity_type": "resolved_business_entity",
                    "original_entity_text": resolution.extracted_value,
                    "normalized_entity_text": resolution.extracted_value,
                    "resolved_entity_value": resolution.matched_value,
                    "resolved_entity_type": "business_identifier",
                    "resolved_table": resolution.resolved_table,
                    "resolved_column": resolution.resolved_column,
                    "resolution_confidence": resolution.confidence,
                    "resolution_method": resolution.match_type,
                    "supporting_evidence_ids": [resolution.evidence_id] if resolution.evidence_id else [],
                }
                for resolution in entity_resolution.resolutions
                if resolution.matched_value
            ] + [
                {
                    "entity_type": "entity_resolution_diagnostic",
                    "resolution_trace_id": resolution.evidence_id,
                    "internal_match_id": resolution.evidence_id,
                    "candidate_id": "",
                    "resolver_rule_id": resolution.match_type,
                    **asdict(resolution),
                }
                for resolution in entity_resolution.resolutions
            ],
            default=str,
        ),
        "evidence": _evidence_to_json(evidence),
        "sql_queries": json.dumps([item.sql for item in evidence], default=str),
        "report_path": str(generated_report.directory),
        "report_storage": json.dumps(report_storage_references(generated_report), default=str),
        "report_snapshot": json.dumps(report_to_dict(report), default=str),
        "verification_checks": json.dumps([asdict(item) for item in verification_checks], default=str),
        "ai_debug_trace": json.dumps(sanitize_ai_trace(ai_debug_trace or {}), default=str),
        "answer_provenance": answer_provenance,
        "primary_entity": json.dumps({
            "table": evidence_focus.affected_object,
            "reason": evidence_focus.affected_object_reason,
        }, default=str),
        "selected_business_key": json.dumps({
            "value": evidence_focus.selected_business_key_value,
            "reason": evidence_focus.business_key_reason,
        }, default=str),
        "relationship_proof": json.dumps(relationship_proof, default=str),
        "evidence_gate_reason": evidence_gate_reason,
        "structured_result": json.dumps({
            "ranked_objects": [asdict(item) for item in ranking.objects],
            "procedures": [asdict(item) for item in procedure_analysis],
            "root_cause_claims": [asdict(item) for item in reasoning.likely_root_causes],
            "recommended_fix": reasoning.recommended_fix,
            "response_type": reasoning.response_type,
            "confidence": confidence,
            "raw_extracted_entity": transfer_normalization_trace.raw_extracted_entity,
            "normalized_entity": transfer_normalization_trace.normalized_entity,
            "entity_type": transfer_normalization_trace.entity_type,
            "normalization_rule_used": transfer_normalization_trace.normalization_rule_used,
            "selected_primary_object": evidence_focus.affected_object,
            "selected_business_key": evidence_focus.selected_business_key_value,
            "primary_entity": {
                "table": evidence_focus.affected_object,
                "reason": evidence_focus.affected_object_reason,
            },
            "selected_business_key": {
                "value": evidence_focus.selected_business_key_value,
                "reason": evidence_focus.business_key_reason,
            },
            "relationship_proof": relationship_proof,
            "evidence_gate_reason": evidence_gate_reason,
        }, default=str),
    }
    return answer, list(dict.fromkeys(source_names)), confidence, generated_report.links(), investigation_metadata


def _apply_entity_resolutions(entities, result: EntityResolutionResult):
    matched = {
        resolution.extracted_value.casefold(): resolution.matched_value
        for resolution in result.resolutions
        if resolution.matched_value
    }
    return replace(
        entities,
        entities=[
            ExtractedEntity(entity.entity_type, matched.get(entity.value.casefold(), entity.value))
            for entity in entities.entities
        ],
    )


def _entity_resolution_blocked_answer(connection_name: str, entities, result: EntityResolutionResult):
    metadata = _empty_investigation_metadata()
    metadata["detected_intent"] = f"INSUFFICIENT_DATABASE_EVIDENCE:ENTITY_{result.status.upper()}"
    metadata["extracted_entities"] = json.dumps(
        [
            {"entity_type": entity.entity_type, "value": entity.value}
            for entity in entities.entities
        ] + [
            {"entity_type": "entity_resolution", **asdict(resolution)}
            for resolution in result.resolutions
        ],
        default=str,
    )
    if result.status == "ambiguous":
        message = "AMBIGUOUS_ENTITY: Multiple plausible records matched. Select a candidate or request human review before investigation continues."
    elif result.status == "blocked":
        message = "ENTITY_LOOKUP_BLOCKED: The read-only candidate lookup was blocked; the identifier was not confirmed."
    else:
        message = "ENTITY_NOT_FOUND: No exact or safe partial database match confirmed the supplied identifier."
    return message, [connection_name], 0.0, None, metadata


def _expand_related_id_evidence(connector, metadata, evidence):
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for expand related id evidence within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    related = []
    seen_sql = {item.sql for item in evidence}
    id_values: dict[str, set[Any]] = {}
    for item in evidence:
        for row in item.rows:
            for key, value in row.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized_key.endswith("id") and value not in (None, ""):
                    id_values.setdefault(key, set()).add(value)
    related_tables = sorted(
        metadata.tables[:12],
        key=lambda table: (not is_diagnostic_object(table.name), -table.score, table.name),
    )
    for table in related_tables:
        for column in table.columns:
            if column not in id_values:
                continue
            values = list(id_values[column])[:5]
            literals = ", ".join(
                str(value) if isinstance(value, int)
                else "'" + str(value).replace("'", "''") + "'"
                for value in values
                if isinstance(value, (int, str))
            )
            if not literals:
                continue
            sql = f"SELECT {', '.join(table.columns[:8])} FROM {table.name} WHERE {column} IN ({literals})"
            if sql in seen_sql:
                continue
            seen_sql.add(sql)
            try:
                rows = connector.execute_read_only_query(sql, limit=25)
                if rows:
                    from legacydb_copilot.services.evidence_execution_service import EvidenceResult

                    related.append(
                        EvidenceResult(
                            (
                                f"Inspect duplicate correlated rows by {column} in {table.name}"
                                if len(rows) > 1
                                else f"Inspect correlated rows by {column} in {table.name}"
                            ),
                            sql,
                            rows,
                            evidence_id=f"SQL-{len(evidence) + len(related) + 1}",
                        )
                    )
            except Exception:
                continue
    return related[:8]


@router.post("/ask", response_model=ChatAskResponse, status_code=status.HTTP_201_CREATED)
def ask_chat_question(
    payload: ChatAskRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> dict[str, object]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Main AI Chat orchestration endpoint for database investigations.

    Input:
        ChatAskRequest containing organization, workspace, user, conversation, and natural-language question.

    Output:
        Chat response, investigation id, confidence, sources, and generated report links.

    Called by:
        Browser AI Chat page when the user clicks Ask AI.

    Flow:
        Auth/RBAC -> prompt safety -> intent/entity/context discovery -> safe SQL -> evidence -> reasoning ->
        verification suggestions -> report generation -> history persistence.

    Safety:
        LLM reasoning is optional and evidence-grounded. SQL is generated/executed only through the safe read-only
        planner and validators.
    """

    assert_same_organization(current_user, payload.organization_id)
    assert_same_user(current_user, payload.user_id)
    require_workspace_access(db, current_user, payload.workspace_id, action="investigate")
    selected_connection = _find_workspace_connection(db, payload)
    conversation = _get_or_create_conversation(db, payload)
    report = analyze_prompt(payload.question, has_sources=True)
    if report.findings:
        answer = _build_placeholder_answer(payload.question, report.findings)
        sources: list[str] = []
        confidence = report.confidence
        report_links = None
        investigation_metadata = _empty_investigation_metadata()
    else:
        try:
            answer, sources, confidence, report_links, investigation_metadata = _run_dynamic_investigation(
                db,
                payload,
                current_user.email or current_user.full_name or current_user.id,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Ask AI failed while collecting evidence or generating the report: {exc}",
            ) from exc

    user_message = ChatMessageModel(
        conversation_id=conversation.id,
        role="user",
        content=payload.question,
        confidence=None,
        source_count=0,
        requires_human_review=False,
    )
    assistant_message = ChatMessageModel(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        confidence=confidence,
        source_count=len(sources),
        requires_human_review=report.requires_human_review,
    )
    db.add(user_message)
    db.add(assistant_message)
    investigation_id = investigation_metadata.get("investigation_id")
    if not investigation_metadata.get("report_storage") and report_links and investigation_id:
        investigation_metadata["report_storage"] = json.dumps(
            {
                link.rsplit("/", 1)[-1]: f"reports/history/{investigation_id}/{link.rsplit('/', 1)[-1]}"
                for key, link in report_links.items()
                if key != "investigation_id" and isinstance(link, str)
            }
        )
    investigation_status = _investigation_status(
        investigation_metadata.get("detected_intent"),
        investigation_metadata.get("answer_provenance"),
    )
    terminal_ai_trace = _terminal_ai_trace(investigation_metadata)
    investigation = InvestigationModel(
        id=investigation_id,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        connection_id=selected_connection.id,
        connection_name=selected_connection.name,
        conversation_id=conversation.id,
        created_by_id=current_user.id,
        user_question=payload.question,
        detected_intent=investigation_metadata["detected_intent"],
        extracted_entities_json=investigation_metadata["extracted_entities"],
        evidence_json=investigation_metadata["evidence"],
        sql_queries_json=investigation_metadata["sql_queries"],
        ai_answer=answer,
        confidence_score=confidence,
        report_path=investigation_metadata["report_path"],
        report_storage_json=investigation_metadata.get("report_storage", "{}"),
        report_snapshot_json=investigation_metadata.get("report_snapshot", ""),
        ai_debug_trace_json=json.dumps(sanitize_ai_trace(terminal_ai_trace), default=str),
        status=investigation_status,
    )
    db.add(investigation)
    db.flush()
    record_audit_event(
        db,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        user_id=current_user.id,
        action="INVESTIGATION_STARTED",
        resource_type="investigation",
        resource_id=investigation.id,
        status="success",
        metadata={"detected_intent": investigation.detected_intent},
    )
    for check in json.loads(investigation_metadata.get("verification_checks", "[]") or "[]"):
        db.add(
            VerificationCheckModel(
                organization_id=payload.organization_id,
                workspace_id=payload.workspace_id,
                investigation_id=investigation_id,
                claim=check.get("claim", ""),
                purpose=check.get("purpose", ""),
                claim_being_verified=check.get("claim_being_verified", check.get("claim", "")),
                evidence_logic=check.get("evidence_logic", ""),
                expected_result_explanation=check.get("expected_result_explanation", ""),
                interpretation=check.get("interpretation", ""),
                conclusion_template=check.get("conclusion_template", ""),
                verification_sql=check.get("verification_sql", ""),
                expected_result=check.get("expected_result", ""),
                risk_level=check.get("risk_level", "Read-only"),
                source=check.get("source", ""),
                status=check.get("status", "Pending"),
                notes=check.get("notes", ""),
            )
        )
    db.commit()
    db.refresh(conversation)
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(investigation)

    return {
        "conversation": conversation,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "findings": [finding.value for finding in report.findings],
        "confidence": confidence,
        "requires_human_review": report.requires_human_review,
        "sources": sources,
        "report": report_links,
        "investigation_id": investigation.id,
        "connection_id": selected_connection.id,
        "connection_name": selected_connection.name,
    }


def _get_verification_investigation(
    db: Session,
    investigation_id: str,
    current_user,
) -> InvestigationModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for get verification investigation within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_resource_owner_workspace(db, current_user, investigation, action="verify")
    return investigation


def _active_connector_for_investigation(db: Session, investigation: InvestigationModel):
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for active connector for investigation within chat.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in chat.py.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    connection = (
        db.query(DatabaseConnectionModel)
        .filter(
            DatabaseConnectionModel.organization_id == investigation.organization_id,
            DatabaseConnectionModel.workspace_id == investigation.workspace_id,
            DatabaseConnectionModel.is_active.is_(True),
        )
        .order_by(DatabaseConnectionModel.updated_at.desc())
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="No active database connection found for verification")
    try:
        connector = get_connection_pool().get_or_create(
            connection.id,
            DatabaseEngine(connection.engine),
            _build_connection_string(connection),
        )
        connector.connect()
        return connector
    except (DatabaseConnectionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Verification connection failed: {exc}") from exc


@router.get("/investigations/{investigation_id}/verification-checks", response_model=list[VerificationCheckRead])
def list_verification_checks(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> list[VerificationCheckModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list verification checks within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    investigation = _get_verification_investigation(db, investigation_id, current_user)
    return list(
        db.query(VerificationCheckModel)
        .filter(VerificationCheckModel.investigation_id == investigation.id)
        .order_by(VerificationCheckModel.created_at.asc())
        .all()
    )


@router.post("/verification-checks/{check_id}/run", response_model=VerificationCheckRead)
def run_verification_check(
    check_id: str,
    payload: VerificationRunRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> VerificationCheckModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles run verification check within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    check = db.get(VerificationCheckModel, check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Verification check not found")
    investigation = _get_verification_investigation(db, check.investigation_id, current_user)
    connector = _active_connector_for_investigation(db, investigation)
    sql = (payload.verification_sql or check.verification_sql).strip()
    result = execute_verification_check(
        connector=connector,
        claim=check.claim,
        verification_sql=sql,
        expected_result=check.expected_result,
        source=check.source,
        verified_by=current_user.email or current_user.full_name or current_user.id,
    )[0]
    check.verification_sql = sql
    check.actual_result_summary = result.actual_result_summary
    check.status = result.status
    check.confidence_impact = result.confidence_impact
    check.notes = result.notes
    check.conclusion_template = result.conclusion_template
    check.verified_by_id = current_user.id
    check.verified_by = result.verified_by
    check.verified_at = datetime.utcnow()
    record_audit_event(
        db,
        organization_id=check.organization_id,
        workspace_id=check.workspace_id,
        user_id=current_user.id,
        action="VERIFICATION_SQL_EXECUTED",
        resource_type="verification_check",
        resource_id=check.id,
        status=result.status,
        metadata={"investigation_id": investigation.id, "source": check.source},
    )
    _regenerate_report_with_verification(db, investigation)
    db.commit()
    db.refresh(check)
    return check


@router.post("/verification-checks/{check_id}/skip", response_model=VerificationCheckRead)
def skip_verification_check(
    check_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> VerificationCheckModel:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles skip verification check within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    check = db.get(VerificationCheckModel, check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Verification check not found")
    investigation = _get_verification_investigation(db, check.investigation_id, current_user)
    check.status = "Skipped"
    check.actual_result_summary = "Skipped by user."
    check.confidence_impact = "No confidence impact"
    check.verified_by_id = current_user.id
    check.verified_by = current_user.email or current_user.full_name or current_user.id
    check.verified_at = datetime.utcnow()
    record_audit_event(
        db,
        organization_id=check.organization_id,
        workspace_id=check.workspace_id,
        user_id=current_user.id,
        action="VERIFICATION_SQL_SKIPPED",
        resource_type="verification_check",
        resource_id=check.id,
        status="skipped",
        metadata={"investigation_id": investigation.id},
    )
    _regenerate_report_with_verification(db, investigation)
    db.commit()
    db.refresh(check)
    return check


@router.post("/investigations/{investigation_id}/verification-checks/run-all", response_model=VerificationRunAllResponse)
def run_all_verification_checks(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> dict[str, object]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles run all verification checks within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    investigation = _get_verification_investigation(db, investigation_id, current_user)
    connector = _active_connector_for_investigation(db, investigation)
    checks = list(
        db.query(VerificationCheckModel)
        .filter(
            VerificationCheckModel.investigation_id == investigation.id,
            VerificationCheckModel.status == "Pending",
        )
        .order_by(VerificationCheckModel.created_at.asc())
        .all()
    )
    verified_by = current_user.email or current_user.full_name or current_user.id
    for check in checks:
        result = execute_verification_check(
            connector=connector,
            claim=check.claim,
            verification_sql=check.verification_sql,
            expected_result=check.expected_result,
            source=check.source,
            verified_by=verified_by,
        )[0]
        check.actual_result_summary = result.actual_result_summary
        check.status = result.status
        check.confidence_impact = result.confidence_impact
        check.notes = result.notes
        check.conclusion_template = result.conclusion_template
        check.verified_by_id = current_user.id
        check.verified_by = result.verified_by
        check.verified_at = datetime.utcnow()
        record_audit_event(
            db,
            organization_id=check.organization_id,
            workspace_id=check.workspace_id,
            user_id=current_user.id,
            action="VERIFICATION_SQL_EXECUTED",
            resource_type="verification_check",
            resource_id=check.id,
            status=result.status,
            metadata={"investigation_id": investigation.id, "source": check.source, "run_all": True},
        )
    links = _regenerate_report_with_verification(db, investigation)
    db.commit()
    return {
        "checks": list(
            db.query(VerificationCheckModel)
            .filter(VerificationCheckModel.investigation_id == investigation.id)
            .order_by(VerificationCheckModel.created_at.asc())
            .all()
        ),
        "report": links,
    }


@router.get("/conversations", response_model=list[ChatConversationRead])
def list_chat_conversations(
    organization_id: str,
    workspace_id: str,
    user_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> list[ChatConversationModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list chat conversations within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    assert_same_user(current_user, user_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    return list(
        db.query(ChatConversationModel)
        .filter(
            ChatConversationModel.organization_id == organization_id,
            ChatConversationModel.workspace_id == workspace_id,
            ChatConversationModel.user_id == user_id,
        )
        .order_by(ChatConversationModel.updated_at.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead])
def list_chat_messages(
    conversation_id: str,
    organization_id: str,
    workspace_id: str,
    user_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> list[ChatMessageModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles list chat messages within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        FastAPI routing layer and browser UI actions.
    
    Where it fits in the flow:
        Auth/RBAC -> intent/entities -> context -> safe SQL -> evidence -> reasoning -> verification suggestions -> report.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    assert_same_organization(current_user, organization_id)
    assert_same_user(current_user, user_id)
    require_workspace_access(db, current_user, workspace_id, action="read")
    conversation = db.get(ChatConversationModel, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if (
        conversation.organization_id != organization_id
        or conversation.workspace_id != workspace_id
        or conversation.user_id != user_id
    ):
        raise HTTPException(status_code=403, detail="Conversation is outside this tenant scope")
    return list(
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.conversation_id == conversation_id)
        .order_by(ChatMessageModel.created_at.asc())
        .all()
    )

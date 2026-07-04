from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from legacydb_copilot.ai import SafetyFinding, analyze_prompt
from legacydb_copilot.agents.context_discovery_agent import discover_context
from legacydb_copilot.agents.entity_extraction_agent import extract_entities
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
from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate, unreproduced_reasoning
from legacydb_copilot.services.evidence_verification_agent import execute_verification_check, suggest_verification_checks
from legacydb_copilot.services.investigation_reports import generate_investigation_report_files
from legacydb_copilot.services.investigation_mode_service import (
    InvestigationMode,
    ModeClassification,
    classify_investigation_mode,
)
from legacydb_copilot.services.llm_reasoning_service import (
    enhance_reasoning_with_llm,
    llm_reasoning_enabled,
)
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

router = APIRouter(prefix="/chat", tags=["chat"])


def _title_from_question(question: str) -> str:
    clean = " ".join(question.strip().split())
    return clean[:72] or "New conversation"


def _build_placeholder_answer(question: str, findings: tuple[SafetyFinding, ...]) -> str:
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
    return "```sql\n" + sql.strip() + "\n```"



def _find_workspace_connection(db: Session, payload: ChatAskRequest) -> DatabaseConnectionModel | None:
    return (
        db.query(DatabaseConnectionModel)
        .filter(
            DatabaseConnectionModel.organization_id == payload.organization_id,
            DatabaseConnectionModel.workspace_id == payload.workspace_id,
            DatabaseConnectionModel.is_active.is_(True),
        )
        .order_by(DatabaseConnectionModel.created_at.desc())
        .first()
    )



def _get_or_create_conversation(
    db: Session,
    payload: ChatAskRequest,
) -> ChatConversationModel:
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
    return json.dumps(
        [
            {
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
    return {
        "investigation_id": None,
        "detected_intent": "UNKNOWN",
        "extracted_entities": "[]",
        "evidence": "[]",
        "sql_queries": "[]",
        "report_path": "",
        "report_snapshot": "",
        "verification_checks": "[]",
    }


def _approved_knowledge_context(db: Session, payload: ChatAskRequest) -> str:
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
    return {token.strip(".,:;()[]{}").lower() for token in value.split() if len(token.strip(".,:;()[]{}")) >= 3}


def _format_retrieved_items(items, *, empty: str) -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(
        f"- {item.title} ({item.source}, score {int(item.score * 100)}%): {item.snippet[:240]}"
        for item in items
    )


def _previous_investigation_matches(db: Session, payload: ChatAskRequest, *, limit: int = 5) -> list[InvestigationModel]:
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
    if intent and intent.intent == InvestigationIntent.STORED_PROCEDURE_ANALYSIS:
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
        "Object Not Found In Connected Database.\n\n"
        "The app stopped before generating root-cause hypotheses because the primary business object from the question was not found in the connected database metadata.\n\n"
        "## Stage 1 - Understand the Question\n"
        f"- Investigation Mode: {mode.mode.value}\n"
        f"- Detected Intent: {intent.intent.value}\n"
        f"- Target Object Searched: {missing_target}\n\n"
        "## Searched Sources\n"
        + "\n".join(f"- {item}" for item in searched)
        + "\n\n## Semantic Matches\n"
        f"{_format_retrieved_items(semantic_matches, empty='No semantic document matches found.')}\n\n"
        "## Confidence\n"
        f"- {int(confidence * 100)}%\n"
        "- Confidence is low because the target object could not be resolved from connected schema evidence.\n\n"
        "## Recommendation\n"
        "- Confirm that this workspace is connected to the correct customer database.\n"
        "- Check whether the object uses a different name in this database.\n"
        "- Upload or approve business process documents that map business terms to physical table/procedure names.\n"
        "- Ask again after the correct database or object mapping is available."
    )
    report_links, investigation_id, report_path = _generate_lightweight_report(
        db=db,
        payload=payload,
        generated_by=generated_by,
        title=f"Object Not Found - {payload.question}",
        mode=mode.mode.value,
        database_name=database_name,
        confidence=confidence,
        summary="Reported issue could not be investigated because the target object was not found in connected database evidence.",
        sections=[
            ReportSection(
                title="Object Not Found",
                items=[
                    f"Target Object Searched: {missing_target}",
                    "Root-cause hypotheses were not generated.",
                    "Live SQL evidence queries were not planned for an unresolved target object.",
                ],
            ),
            ReportSection(title="Searched Sources", items=searched),
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
                title="Recommendation",
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
    metadata["detected_intent"] = f"OBJECT_NOT_FOUND:{intent.intent.value}"
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
    settings = Settings.from_env()
    if llm_used:
        return {
            "ai_assisted_reasoning": "Enabled",
            "reason": "OpenAI LLM reasoning was applied after deterministic evidence collection.",
            "evidence_package_sent": "Yes",
            "llm_evidence_validation": "Passed",
            "evidence_citations": "Passed",
        }
    if not settings.openai_api_key:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "OPENAI_API_KEY not configured",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
        }
    if not settings.ai_reasoning_enabled:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "AI_REASONING_ENABLED=false",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
        }
    if not llm_configured:
        return {
            "ai_assisted_reasoning": "Disabled",
            "reason": "LLM provider is not configured for OpenAI evidence-grounded reasoning.",
            "evidence_package_sent": "No",
            "llm_evidence_validation": "Not applicable",
            "evidence_citations": "Not applicable",
        }
    return {
        "ai_assisted_reasoning": "Enabled",
        "reason": "OpenAI was configured, but deterministic output was kept because no usable evidence-cited AI reasoning was returned.",
        "evidence_package_sent": "Yes",
        "llm_evidence_validation": "Failed",
        "evidence_citations": "Failed",
    }


def _verification_sections_from_models(checks: list[VerificationCheckModel]) -> list[ReportSection]:
    suggested_rows = [
        {
            "Claim to verify": item.claim,
            "Generated read-only SQL": item.verification_sql,
            "Expected result": item.expected_result,
            "Risk level": item.risk_level,
            "Source": item.source,
            "Status": item.status,
        }
        for item in checks
    ]
    executed_rows = [
        {
            "Claim": item.claim,
            "SQL executed": item.verification_sql,
            "Expected result": item.expected_result,
            "Actual result summary": item.actual_result_summary,
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
                    columns=["Claim to verify", "Generated read-only SQL", "Expected result", "Risk level", "Source", "Status"],
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
                    columns=["Claim", "SQL executed", "Expected result", "Actual result summary", "Status", "Confidence impact", "Timestamp", "Verified by"],
                    rows=executed_rows
                    or [{"Claim": "No checks have been executed yet", "SQL executed": "", "Expected result": "", "Actual result summary": "", "Status": "Pending", "Confidence impact": "", "Timestamp": "", "Verified by": ""}],
                )
            ],
        ),
    ]


def _regenerate_report_with_verification(db: Session, investigation: InvestigationModel) -> dict[str, str] | None:
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
    return generated.links()


def _run_dynamic_investigation(
    db: Session,
    payload: ChatAskRequest,
    generated_by: str,
) -> tuple[str, list[str], float, dict[str, str] | None, dict[str, Any]]:
    intent = detect_intent(payload.question)
    entities = extract_entities(payload.question)
    mode = classify_investigation_mode(payload.question, intent)
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
        connector = get_connection_pool().get_or_create(
            connection.id,
            DatabaseEngine(connection.engine),
            _build_connection_string(connection),
        )
        connector.connect()
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
    )
    target_missing, missing_target, _ = _target_object_not_found(payload.question, context.metadata, intent)
    if target_missing:
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
    procedure_analysis = analyze_stored_procedures(connector, ranking.metadata.procedures)
    plan = build_investigation_plan(intent.intent, ranking.metadata, entities)
    evidence = execute_evidence_plan(connector, plan)
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
    )
    if evidence_gate.required and not evidence_gate.reproduced:
        reasoning = unreproduced_reasoning(evidence_gate)
        llm_configured = llm_reasoning_enabled()
        llm_used = False
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
        llm_configured = llm_reasoning_enabled()
        enhanced_reasoning = enhance_reasoning_with_llm(
            question=payload.question,
            intent=intent,
            deterministic_reasoning=reasoning,
            evidence=evidence,
            correlated_evidence=correlated_evidence,
            procedure_analysis=procedure_analysis,
            documents=context.documents,
            evidence_focus=evidence_focus,
        )
        llm_used = enhanced_reasoning is not reasoning
        reasoning = enhanced_reasoning
    recommendation = recommend_actions(
        intent=intent.intent,
        reasoning=reasoning,
        correlated_evidence=correlated_evidence,
    )
    confidence = score_confidence(ranking.metadata, evidence, context.documents, evidence_focus)
    confidence_notes = confidence_factors(ranking.metadata, evidence, context.documents, evidence_focus)
    if evidence_gate.required and not evidence_gate.reproduced:
        confidence = min(confidence, 0.35)
        confidence_notes.extend(f"- Evidence gate blocked root-cause analysis: {item}" for item in evidence_gate.blocking_reasons)
    verification_checks = []
    if Settings.from_env().verification_agent_enabled:
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
        verification_checks=verification_checks,
        verification_results=[],
    )
    workspace = db.get(WorkspaceModel, payload.workspace_id)
    report = compose_report(
        bundle=bundle,
        workspace_name=workspace.name if workspace else payload.workspace_id,
        database_name=f"{connection.name} ({connection.engine})",
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
        + "\n\n".join(_sql_block(item.sql) for item in evidence[:5])
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
    investigation_metadata = {
        "investigation_id": report.cover.investigation_id,
        "detected_intent": intent.intent.value,
        "extracted_entities": json.dumps(
            [
                {
                    "entity_type": entity.entity_type,
                    "value": entity.value,
                }
                for entity in entities.entities
            ],
            default=str,
        ),
        "evidence": _evidence_to_json(evidence),
        "sql_queries": json.dumps([item.sql for item in evidence], default=str),
        "report_path": str(generated_report.directory),
        "report_snapshot": json.dumps(report_to_dict(report), default=str),
        "verification_checks": json.dumps([asdict(item) for item in verification_checks], default=str),
    }
    return answer, list(dict.fromkeys(source_names)), confidence, generated_report.links(), investigation_metadata


def _expand_related_id_evidence(connector, metadata, evidence):
    related = []
    seen_sql = {item.sql for item in evidence}
    id_values: dict[str, set[Any]] = {}
    for item in evidence:
        for row in item.rows:
            for key, value in row.items():
                if key.endswith("_id") and value is not None:
                    id_values.setdefault(key, set()).add(value)
    for table in metadata.tables[:8]:
        for column in table.columns:
            if column not in id_values:
                continue
            values = list(id_values[column])[:5]
            literals = ", ".join(str(int(value)) for value in values if isinstance(value, int))
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

                    related.append(EvidenceResult(f"Inspect rows related by {column} in {table.name}", sql, rows))
            except Exception:
                continue
    return related[:8]


@router.post("/ask", response_model=ChatAskResponse, status_code=status.HTTP_201_CREATED)
def ask_chat_question(
    payload: ChatAskRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> dict[str, object]:
    assert_same_organization(current_user, payload.organization_id)
    assert_same_user(current_user, payload.user_id)
    require_workspace_access(db, current_user, payload.workspace_id, action="investigate")
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
    investigation = InvestigationModel(
        id=investigation_id,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
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
        report_snapshot_json=investigation_metadata.get("report_snapshot", ""),
        status="AI_ANSWERED",
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
    }


def _get_verification_investigation(
    db: Session,
    investigation_id: str,
    current_user,
) -> InvestigationModel:
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_resource_owner_workspace(db, current_user, investigation, action="verify")
    return investigation


def _active_connector_for_investigation(db: Session, investigation: InvestigationModel):
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

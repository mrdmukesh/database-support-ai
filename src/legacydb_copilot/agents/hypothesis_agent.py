from __future__ import annotations

from dataclasses import dataclass

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.object_ranking_agent import RankedObject
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class QuestionUnderstanding:
    user_goal: str
    user_hypothesis: str
    business_process: str
    likely_objects: list[str]
    required_evidence: list[str]


@dataclass(frozen=True)
class InvestigationHypothesis:
    hypothesis_id: str
    description: str
    initial_confidence: float
    required_evidence: list[str]
    tables_to_inspect: list[str]
    procedures_to_inspect: list[str]
    logs_to_inspect: list[str]
    documents_to_inspect: list[str]
    sql_focus: list[str]


@dataclass(frozen=True)
class HypothesisEvaluation:
    hypothesis_id: str
    description: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    missing_evidence: list[str]
    confidence: float
    reason: str


@dataclass(frozen=True)
class HypothesisReasoningResult:
    understanding: QuestionUnderstanding
    hypotheses: list[InvestigationHypothesis]
    evaluations: list[HypothesisEvaluation]
    ranked_root_causes: list[HypothesisEvaluation]
    event_chain: list[str]
    process_graph: list[tuple[str, str]]


def understand_question(
    *,
    question: str,
    intent: IntentResult,
    entities: EntityExtractionResult,
    ranked_objects: list[RankedObject],
) -> QuestionUnderstanding:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles understand question within the Database Support AI application flow.
    
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
    business_process = entities.likely_module or "database process"
    object_names = [item.name for item in ranked_objects[:6]]
    entity_values = [entity.value for entity in entities.entities if entity.entity_type not in {"application_name"}]
    if intent.intent == InvestigationIntent.DUPLICATE_DATA:
        user_hypothesis = "There should be only one valid record for the affected business key."
    elif intent.intent == InvestigationIntent.MISSING_DATA:
        user_hypothesis = "A downstream record should have been generated but is missing."
    elif intent.intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        user_hypothesis = "The query or process should complete within expected performance limits."
    elif intent.intent == InvestigationIntent.PROCESS_FLOW_BREAK:
        user_hypothesis = "The business process should move from the current step to the next expected step."
    else:
        user_hypothesis = "The database evidence should explain the reported behavior."
    return QuestionUnderstanding(
        user_goal=f"Answer the user question with database evidence: {question}",
        user_hypothesis=user_hypothesis,
        business_process=business_process,
        likely_objects=object_names,
        required_evidence=[
            "Rows for the affected business key(s)" if entity_values else "Rows matching the business process",
            "Relevant table relationships and indexes",
            "Stored procedure read/write behavior",
            "Job, audit, or error-log evidence when available",
            "Approved knowledge and uploaded documents when relevant",
        ],
    )


def generate_hypotheses(
    *,
    intent: IntentResult,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
) -> list[InvestigationHypothesis]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles generate hypotheses within the Database Support AI application flow.
    
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
    tables = [table.name for table in metadata.tables[:5]]
    procedures = metadata.procedures[:5]
    logs = [table.name for table in metadata.tables if any(term in table.name.lower() for term in ("log", "audit", "history", "job", "batch"))][:5]
    docs = ["Uploaded documents", "Approved knowledge articles"]

    templates: list[tuple[str, float, list[str], list[str]]] = []
    relationship_edges = [
        (table.name, str(fk.get("referred_table") or ""))
        for table in metadata.tables
        for fk in table.foreign_keys or []
        if fk.get("referred_table")
    ]
    natural_key_tables = [
        table.name
        for table in metadata.tables
        if any(column.lower().endswith(("_number", "_code", "_ref", "_key")) for column in table.columns)
    ]
    status_tables = [
        table.name
        for table in metadata.tables
        if any("status" in column.lower() or "state" in column.lower() for column in table.columns)
    ]
    indexed_tables = [table.name for table in metadata.tables if table.indexes]

    if relationship_edges:
        child, parent = relationship_edges[0]
        templates.append(
            (
                f"Relationship path {parent} -> {child} does not contain the expected related row or transition evidence.",
                0.48,
                ["Parent-to-child relationship evidence", "Rows on both sides of the relationship", "Missing or mismatched related rows"],
                ["foreign keys", "related rows"],
            )
        )
    if status_tables:
        templates.append(
            (
                f"State or status values in {', '.join(status_tables[:3])} may be preventing the expected workflow transition.",
                0.42,
                ["Source row status/state", "Procedure branch or WHERE condition", "Related row evidence"],
                ["status", "state", "procedure guard"],
            )
        )
    if procedures:
        templates.append(
            (
                f"Procedure write/read path may explain the behavior; inspect {', '.join(procedures[:3])}.",
                0.5,
                ["Stored procedure read/write behavior", "Procedure branch or WHERE condition", "Transaction or error handling evidence"],
                ["procedure analysis", "write path", "read path"],
            )
        )
    if logs:
        templates.append(
            (
                f"Operational history or error evidence in {', '.join(logs[:3])} may identify the failed step.",
                0.38,
                ["Job, audit, or error-log evidence", "Timestamps", "Affected keys"],
                ["logs", "history", "audit"],
            )
        )
    if natural_key_tables:
        templates.append(
            (
                f"Natural-key evidence in {', '.join(natural_key_tables[:3])} may show duplicates, mismatches, or missing expected records.",
                0.36,
                ["Business key rows", "Uniqueness/index evidence", "Matching rows for extracted entities"],
                ["business key", "indexes", "matching rows"],
            )
        )
    if intent.intent == InvestigationIntent.PERFORMANCE_INVESTIGATION and metadata.tables:
        templates.append(
            (
                f"Access path for {metadata.tables[0].name} may be inefficient based on row volume, predicates, indexes, or execution plan.",
                0.44 if indexed_tables else 0.5,
                ["EXPLAIN output", "Index metadata", "Predicate columns", "Rows scanned"],
                ["explain", "indexes", "row count"],
            )
        )
    templates.append(
        (
            "Uploaded documents or approved knowledge may describe a business rule or known incident that changes the interpretation of database evidence.",
            0.3,
            ["Approved knowledge and uploaded documents when relevant", "Documented business rules", "Historical incident evidence"],
            ["documents", "knowledge"],
        )
    )

    return [
        InvestigationHypothesis(
            hypothesis_id=f"H{index}",
            description=description,
            initial_confidence=confidence,
            required_evidence=required,
            tables_to_inspect=tables,
            procedures_to_inspect=procedures,
            logs_to_inspect=logs,
            documents_to_inspect=docs,
            sql_focus=focus,
        )
        for index, (description, confidence, required, focus) in enumerate(templates, start=1)
    ]


def evaluate_hypotheses(
    *,
    hypotheses: list[InvestigationHypothesis],
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
) -> list[HypothesisEvaluation]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles evaluate hypotheses within the Database Support AI application flow.
    
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
    evaluations: list[HypothesisEvaluation] = []
    row_text = " ".join(str(row) for item in evidence for row in item.rows[:20])
    evidence_text = " ".join(
        [item.purpose + " " + item.sql for item in evidence]
        + [item.finding + " " + item.support for item in correlated_evidence]
        + [doc.title + " " + doc.snippet for doc in documents]
        + [row_text]
    ).lower()
    non_empty_count = sum(1 for item in evidence if item.rows)
    write_proc_names = [
        rank.procedure
        for rank in (evidence_focus.ranked_procedures if evidence_focus else [])
        if rank.writes_affected_object
    ] or [proc.name for proc in procedure_analysis if proc.tables_written]
    unique_index_hint = any("unique" in str(table_evidence).lower() for table_evidence in correlated_evidence)
    if evidence_focus and evidence_focus.ranked_procedures:
        direct_writer = next(
            (rank for rank in evidence_focus.ranked_procedures if rank.writes_affected_object),
            None,
        )
        duplicate_confirmed = any(
            "duplicate" in item.purpose.lower() and item.rows
            for item in evidence
        )
        if direct_writer:
            support = [
                f"{direct_writer.procedure} directly writes {evidence_focus.affected_object}.",
                "Procedure Analysis confirms tables_written for the affected object.",
            ]
            if duplicate_confirmed:
                support.append("Duplicate child rows were confirmed by parent-child evidence SQL.")
            if direct_writer.error_log_support:
                support.append("Error-log evidence references the direct writer and affected object.")
            evaluations.append(
                HypothesisEvaluation(
                    hypothesis_id="H-DIRECT-WRITER",
                    description=(
                        f"Confirmed direct writer {direct_writer.procedure} is the leading root-cause candidate "
                        f"because it writes affected object {evidence_focus.affected_object}."
                    ),
                    supporting_evidence=support,
                    contradicting_evidence=["No stronger confirmed direct writer was ranked above this procedure."],
                    missing_evidence=(
                        ["Retry/job/audit execution timing is still needed to prove the exact run instance."]
                        if not direct_writer.error_log_support
                        else ["Transaction-level execution timing may still improve proof."]
                    ),
                    confidence=0.92 if duplicate_confirmed else 0.82,
                    reason="Evidence-first ranking prioritizes confirmed writers of the affected object over metadata-only hypotheses.",
                )
            )

    for hypothesis in hypotheses:
        supporting: list[str] = []
        contradicting: list[str] = []
        missing: list[str] = []
        confidence = hypothesis.initial_confidence
        for required in hypothesis.required_evidence:
            required_l = required.lower()
            if any(token in evidence_text for token in required_l.split() if len(token) >= 5):
                supporting.append(required)
                confidence += 0.08
            else:
                missing.append(required)
                confidence -= 0.04
        if non_empty_count:
            supporting.append(f"{non_empty_count} read-only evidence query result(s) returned rows.")
            confidence += min(0.18, non_empty_count * 0.03)
        else:
            missing.append("No safe SQL query returned confirming rows.")
            confidence -= 0.15
        if "procedure" in hypothesis.description.lower() or "retry" in hypothesis.description.lower():
            if write_proc_names:
                supporting.append(f"Procedure(s) directly modifying the affected object: {', '.join(write_proc_names[:3])}.")
                confidence += 0.18
            else:
                missing.append("No stored procedure was confirmed to directly modify the affected object.")
                confidence -= 0.16
        if evidence_focus and "procedure write/read path" in hypothesis.description.lower():
            top_proc = evidence_focus.ranked_procedures[0] if evidence_focus.ranked_procedures else None
            if top_proc and not top_proc.writes_affected_object:
                contradicting.append("Highest-ranked procedure does not directly modify the affected object.")
                confidence -= 0.16
        if "uniqueness" in hypothesis.description.lower() or "unique" in hypothesis.description.lower():
            if unique_index_hint:
                contradicting.append("Some uniqueness/index evidence exists; verify whether it covers the exact business rule.")
                confidence -= 0.08
            else:
                supporting.append("No confirmed uniqueness protection was found in correlated evidence.")
                confidence += 0.08
        if "relationship path" in hypothesis.description.lower():
            if "missing_related_record" in evidence_text:
                supporting.append("Missing related record candidates were confirmed by parent-child relationship SQL.")
                confidence += 0.2
            else:
                missing.append("No confirmed missing related record candidates were returned.")
                confidence -= 0.08
        confidence = max(0.05, min(0.98, confidence))
        reason = "Supported by collected evidence." if supporting else "Unable to confirm. Additional evidence required."
        evaluations.append(
            HypothesisEvaluation(
                hypothesis_id=hypothesis.hypothesis_id,
                description=hypothesis.description,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting or ["No direct contradicting evidence found."],
                missing_evidence=missing or ["No major missing evidence for this hypothesis."],
                confidence=confidence,
                reason=reason,
            )
        )
    return evaluations


def build_event_chain(
    *,
    top_hypothesis: HypothesisEvaluation | None,
    procedure_analysis: list[ProcedureAnalysis],
    correlated_evidence: list[CorrelatedEvidence],
) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles build event chain within the Database Support AI application flow.
    
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
    if top_hypothesis is None or not top_hypothesis.supporting_evidence:
        return ["Unable to confirm. Additional evidence required."]
    chain = ["User-reported condition was mapped to relevant database objects."]
    if correlated_evidence:
        chain.append("Read-only evidence was collected from ranked tables, procedures, logs, documents, or knowledge.")
    write_procs = [proc for proc in procedure_analysis if proc.tables_written]
    if write_procs:
        chain.append(f"Stored procedure analysis found write path(s): {', '.join(proc.name for proc in write_procs[:3])}.")
        chain.append("Those write paths must be checked for idempotency, EXISTS checks, uniqueness checks, and transaction safety.")
    chain.append(f"Most likely explanation: {top_hypothesis.description}")
    chain.append("Conclusion remains bounded by the supporting and missing evidence listed for the hypothesis.")
    return chain


def discover_process_graph(
    *,
    metadata: MetadataSearchResult,
    procedure_analysis: list[ProcedureAnalysis],
) -> list[tuple[str, str]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles discover process graph within the Database Support AI application flow.
    
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
    edges: list[tuple[str, str]] = []
    for proc in procedure_analysis:
        for table in proc.tables_read:
            edges.append((table, proc.name))
        for table in proc.tables_written:
            edges.append((proc.name, table))
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for edge in edges:
        if edge[0] and edge[1] and edge not in seen:
            seen.add(edge)
            result.append(edge)
    return result[:20]


def run_hypothesis_investigation(
    *,
    question: str,
    intent: IntentResult,
    entities: EntityExtractionResult,
    ranked_objects: list[RankedObject],
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
    evidence_focus: EvidenceFocus | None = None,
) -> HypothesisReasoningResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles run hypothesis investigation within the Database Support AI application flow.
    
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
    understanding = understand_question(
        question=question,
        intent=intent,
        entities=entities,
        ranked_objects=ranked_objects,
    )
    hypotheses = generate_hypotheses(intent=intent, entities=entities, metadata=metadata)
    evaluations = evaluate_hypotheses(
        hypotheses=hypotheses,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=documents,
        evidence_focus=evidence_focus,
    )
    ranked = sorted(
        evaluations,
        key=lambda item: (item.hypothesis_id == "H-DIRECT-WRITER", item.confidence),
        reverse=True,
    )
    return HypothesisReasoningResult(
        understanding=understanding,
        hypotheses=hypotheses,
        evaluations=evaluations,
        ranked_root_causes=ranked,
        event_chain=build_event_chain(
            top_hypothesis=ranked[0] if ranked else None,
            procedure_analysis=procedure_analysis,
            correlated_evidence=correlated_evidence,
        ),
        process_graph=discover_process_graph(metadata=metadata, procedure_analysis=procedure_analysis),
    )

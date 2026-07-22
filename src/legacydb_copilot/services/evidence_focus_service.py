from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.problem_phrase_service import parse_problem_phrase, resolve_table_from_terms
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis
from legacydb_copilot.services.transfer_identifier_normalization import typed_transfer_identifier


@dataclass(frozen=True)
class ProcedureRank:
    procedure: str
    score: float
    writes_affected_object: bool
    reads_affected_object: bool
    relationship_to_affected_object: str
    evidence_found: list[str]
    historical_incidents: list[str]
    error_log_support: bool = False
    job_history_support: bool = False


@dataclass(frozen=True)
class EvidenceFocus:
    affected_object: str
    affected_object_reason: str
    inferred_business_key: str | None
    business_key_reason: str
    write_path_graph: list[tuple[str, str]]
    ranked_procedures: list[ProcedureRank]
    confirmed_facts: list[str]
    inferred_findings: list[str]
    hypotheses: list[str]
    self_validation: list[str]
    selected_business_key_value: str | None = None


def build_evidence_focus(
    *,
    question: str,
    intent: InvestigationIntent,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
) -> EvidenceFocus:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles build evidence focus within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    affected_object, affected_reason = _identify_affected_object(question, entities, metadata, evidence)
    business_key, business_key_reason = _infer_business_key(intent, affected_object, entities, metadata, evidence)
    write_graph = _write_path_graph(affected_object, procedure_analysis)
    ranked_procedures = _rank_procedures(
        affected_object=affected_object,
        entities=entities,
        metadata=metadata,
        evidence=evidence,
        correlated_evidence=correlated_evidence,
        procedure_analysis=procedure_analysis,
        documents=documents,
    )
    confirmed = _confirmed_facts(evidence, ranked_procedures, affected_object, business_key)
    inferred = _inferred_findings(intent, ranked_procedures, evidence, documents)
    hypotheses = _hypotheses(intent, affected_object, business_key, ranked_procedures, evidence)
    validation = _self_validation(affected_object, ranked_procedures, confirmed, hypotheses)
    return EvidenceFocus(
        affected_object=affected_object or "Not determined",
        affected_object_reason=affected_reason,
        inferred_business_key=business_key,
        business_key_reason=business_key_reason,
        write_path_graph=write_graph,
        ranked_procedures=ranked_procedures,
        confirmed_facts=confirmed,
        inferred_findings=inferred,
        hypotheses=hypotheses,
        self_validation=validation,
        selected_business_key_value=_selected_business_key_value(entities, affected_object),
    )


def _identify_affected_object(
    question: str,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
) -> tuple[str, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for identify affected object within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    table_scores: dict[str, float] = {table.name: 0.0 for table in metadata.tables}
    table_lookup = {table.name.lower(): table.name for table in metadata.tables}
    leaf_lookup: dict[str, list[str]] = {}
    for table in metadata.tables:
        leaf_lookup.setdefault(table.name.lower().split(".")[-1], []).append(table.name)
    question_l = question.lower()
    transfer_target = _explicit_transfer_target(question, entities, metadata, evidence)
    if transfer_target:
        return transfer_target, "Selected from exact TRF-<digits> identifier evidence on transfers; diagnostic integration records remain supporting evidence only."
    explicit_write_target = _explicit_write_target(question, metadata)
    if explicit_write_target:
        return explicit_write_target.name, "Locked from explicit procedure write-target phrase such as update/insert into <object>; unrelated evidence rows cannot override it."
    proven_entity_target = _proven_entity_target(metadata, evidence)
    if proven_entity_target:
        return proven_entity_target, "Selected from the unique table whose bounded entity-proof query returned the requested identifier; generic business nouns cannot override database-proven entity provenance."
    problem = parse_problem_phrase(question)
    phrase_target = resolve_table_from_terms(problem.target_terms, metadata)
    if phrase_target:
        cause_text = f"; secondary cause terms ignored for target selection: {', '.join(problem.secondary_cause_terms[:6])}" if problem.secondary_cause_terms else ""
        return phrase_target.name, f"Selected from main problem phrase '{problem.phrase}' ({problem.issue_kind}); parent and secondary-cause terms do not override the target{cause_text}."
    duplicate_target = _duplicate_target_table(question, metadata)
    if duplicate_target:
        return duplicate_target.name, "Selected duplicated object from question phrase such as duplicate/two/multiple <object>; parent identifiers do not override the duplicated target."
    for table in metadata.tables:
        if table.name.lower() in question_l:
            table_scores[table.name] += 2.0
        table_scores[table.name] += table.score * 0.2
    for item in evidence:
        sql_tables = _tables_in_sql(item.sql)
        row_weight = 3.0 if item.rows else 0.5
        purpose_l = item.purpose.lower()
        for sql_table in sql_tables:
            sql_name = sql_table.lower()
            table = table_lookup.get(sql_name)
            if table is None:
                leaf_matches = leaf_lookup.get(sql_name.split(".")[-1], [])
                table = leaf_matches[0] if len(leaf_matches) == 1 else sql_table
            if table in table_scores:
                metadata_relevance = table_scores[table] > 0 or table.lower() in question_l
                if not metadata_relevance:
                    continue
                table_scores[table] += row_weight
                if any(term in purpose_l for term in ("duplicate", "missing", "inspect", "confirm", "related")):
                    table_scores[table] += 1.0
    if not table_scores:
        return "", "No table metadata or SQL evidence was available."
    selected, score = max(table_scores.items(), key=lambda item: (item[1], item[0]))
    if score <= 0:
        return selected, "Selected first available table because no stronger evidence identified a target."
    return selected, "Selected from metadata/question matches plus SQL evidence on those matched candidates; returned rows alone cannot select an affected object."


def _explicit_transfer_target(
    question: str,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
) -> str | None:
    transfer_id = typed_transfer_identifier(entities)
    if not transfer_id:
        match = re.search(r"\bTRF-\d+\b", question, re.IGNORECASE)
        if not match:
            return None
        transfer_id = match.group(0).upper()
    transfer_tables = [table.name for table in metadata.tables if table.name.lower().split(".")[-1] == "transfers"]
    if not transfer_tables:
        transfer_tables = [table.name for table in metadata.tables if "transfer" in table.name.lower().split(".")[-1]]
    if not transfer_tables:
        return None
    for table_name in transfer_tables:
        for item in evidence:
            if f" in {table_name}" not in item.purpose:
                continue
            if transfer_id.casefold() in item.sql.casefold() and item.rows:
                return table_name
    return None


def _proven_entity_target(
    metadata: MetadataSearchResult, evidence: list[EvidenceResult]
) -> str | None:
    """Return a unique entity-proof table, failing closed when proof spans tables."""
    known = {table.name.casefold(): table.name for table in metadata.tables}
    leaves: dict[str, list[str]] = {}
    for table in metadata.tables:
        leaves.setdefault(table.name.casefold().split(".")[-1], []).append(table.name)
    proven: set[str] = set()
    for item in evidence:
        purpose = item.purpose.casefold()
        if not item.rows or not any(
            marker in purpose
            for marker in ("prove requested entity exists", "entity exact lookup")
        ):
            continue
        for sql_table in _tables_in_sql(item.sql):
            resolved = known.get(sql_table.casefold())
            if resolved is None:
                leaf_matches = leaves.get(sql_table.casefold(), [])
                resolved = leaf_matches[0] if len(leaf_matches) == 1 else None
            if resolved:
                proven.add(resolved)
    return next(iter(proven)) if len(proven) == 1 else None


def _explicit_write_target(question: str, metadata: MetadataSearchResult) -> TableMetadata | None:
    lowered = question.lower()
    if "procedure" not in lowered and "procedures" not in lowered and "stored proc" not in lowered:
        return None
    target_terms: list[str] = []
    for pattern in (
        r"\b(?:insert\s+into|update|write\s+to|writes\s+to|modify|modifies)\s+(?!or\b)([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\b(?:into|in)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
    ):
        target_terms.extend(match.group(1).lower() for match in re.finditer(pattern, lowered))
    for term in target_terms:
        resolved = resolve_table_from_terms([term], metadata)
        if resolved:
            return resolved
    return None


def _infer_business_key(intent: InvestigationIntent, affected_object: str, entities: EntityExtractionResult, metadata: MetadataSearchResult, evidence: list[EvidenceResult]) -> tuple[str | None, str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for infer business key within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    table = _table(metadata, affected_object)
    if table is None:
        return None, "No affected table metadata available."
    transfer_id = _selected_business_key_value(entities, affected_object)
    if transfer_id:
        return transfer_id, "Preserved exact typed transfer identifier from the request; prompt words were not converted into SQL filters."
    parent_key = _parent_business_key_from_duplicate_evidence(evidence)
    if parent_key and intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        return parent_key, "Inferred from parent-child duplicate evidence; supplied business key belongs to the parent object, not the duplicated child object."
    natural_cols = [
        column
        for column in table.columns
        if not _is_primary_key(column, table)
        and re.search(r"(_number|_code|_ref|_key|name)$", column.lower())
    ]
    duplicate_cols = _duplicate_group_columns(evidence)
    for column in duplicate_cols:
        if column in table.columns and not _is_primary_key(column, table):
            return column, "Inferred from duplicate evidence grouped by a non-primary business column."
    if intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION} and natural_cols:
        return natural_cols[0], "Inferred from natural-key column naming; primary key was not used as duplicate key."
    if natural_cols:
        return natural_cols[0], "Inferred from natural-key column naming."
    return None, "No non-primary natural key column was identified."


def _selected_business_key_value(entities: EntityExtractionResult, affected_object: str) -> str | None:
    leaf = affected_object.lower().split(".")[-1]
    if "transfer" not in leaf:
        return None
    return typed_transfer_identifier(entities)


def _parent_business_key_from_duplicate_evidence(evidence: list[EvidenceResult]) -> str | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for parent business key from duplicate evidence within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    for item in evidence:
        purpose = item.purpose.lower()
        sql = item.sql
        if "duplicate" not in purpose and "parent business key" not in purpose and "through" not in purpose:
            continue
        for pattern in (
            r"\bp\.([`\"\[\]\w]+)\s+AS\s+parent_reference\b",
            r"\b([`\"\[\]\w]+)\s+AS\s+parent_reference\b",
            r"\bGROUP\s+BY\s+p\.([`\"\[\]\w]+)\b",
        ):
            match = re.search(pattern, sql, re.I)
            if match:
                column = _clean_identifier(match.group(1))
                if not column.lower().endswith("_id") and column.lower() != "id":
                    return column
    return None


def _rank_procedures(
    *,
    affected_object: str,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    correlated_evidence: list[CorrelatedEvidence],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
) -> list[ProcedureRank]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for rank procedures within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    related = set(_related_tables(affected_object, metadata))
    table = _table(metadata, affected_object)
    requested_columns = _requested_columns(table, entities) if table else set()
    business_ids = {
        entity.value.lower()
        for entity in entities.entities
        if entity.entity_type in {"business_identifier", "exact_id_or_code", "business_key"}
    }
    evidence_text = " ".join([item.purpose + " " + item.sql for item in evidence] + [str(row) for item in evidence for row in item.rows[:5]]).lower()
    correlated_text = " ".join(item.subject + " " + item.finding + " " + item.support for item in correlated_evidence).lower()
    document_text = " ".join(doc.title + " " + doc.snippet for doc in documents).lower()
    ranks: list[ProcedureRank] = []
    affected_l = affected_object.lower()
    for proc in procedure_analysis:
        written = {_clean_identifier(table).lower() for table in proc.tables_written}
        read = {_clean_identifier(table).lower() for table in proc.tables_read}
        proc_text = " ".join([proc.definition_excerpt or "", *proc.business_rules]).lower()
        writes_affected = affected_l in written
        reads_affected = affected_l in read
        relationship = "direct write" if writes_affected else "direct read" if reads_affected else "related object" if (written | read) & related else "none confirmed"
        evidence_found: list[str] = []
        historical: list[str] = []
        error_support = _error_log_supports(proc.name, affected_object, evidence)
        job_support = _job_history_supports(proc.name, evidence)
        score = 0.0
        if writes_affected:
            score += 20.0
            evidence_found.append(f"Procedure writes affected object {affected_object}.")
        if reads_affected:
            score += 3.0
            evidence_found.append(f"Procedure reads affected object {affected_object}.")
        if error_support:
            score += 12.0
            evidence_found.append("Error-log evidence references this procedure and the affected object.")
        if job_support:
            score += 6.0
            evidence_found.append("Job/history evidence references this procedure.")
        if (written | read) & related:
            score += 2.0
            evidence_found.append("Procedure touches an upstream/downstream related object.")
        column_hits = {column for column in requested_columns if column.lower() in proc_text}
        if column_hits and (writes_affected or reads_affected or (written | read) & related):
            score += 3.0 + len(column_hits)
            evidence_found.append("Procedure text references requested column(s): " + ", ".join(sorted(column_hits)) + ".")
        id_hits = {value for value in business_ids if value and value in proc_text}
        if id_hits and (writes_affected or reads_affected):
            score += 2.0
            evidence_found.append("Procedure text references requested business identifier(s).")
        proc_l = proc.name.lower()
        if proc_l in evidence_text or proc_l in correlated_text:
            score += 3.0
            evidence_found.append("Procedure name appears in collected SQL/correlated evidence.")
        if proc_l in document_text:
            score += 2.0
            historical.append("Procedure appears in retrieved documents or approved knowledge.")
        if proc.missing_exists_checks and writes_affected:
            score += 1.5
            evidence_found.append("Direct write path lacks an EXISTS / NOT EXISTS idempotency check in parsed procedure text.")
        if proc.missing_uniqueness_checks and writes_affected:
            score += 1.5
            evidence_found.append("Direct write path lacks uniqueness/duplicate check in parsed procedure text.")
        if writes_affected and proc.insert_statements and (proc.missing_exists_checks or proc.missing_uniqueness_checks):
            score += 1.0
            evidence_found.append("INSERT logic writes the affected object without confirmed duplicate-prevention guards.")
        if writes_affected and proc.dynamic_sql:
            score += 1.0
            evidence_found.append("Dynamic SQL touches the affected object; review generated statements and bind predicates.")
        if writes_affected and not proc.transactions:
            evidence_found.append("No explicit transaction handling was detected around the affected-object write path.")
        if writes_affected and not proc.try_catch:
            evidence_found.append("No explicit exception/retry guard was detected in parsed procedure text.")
        if score <= 0:
            continue
        ranks.append(
            ProcedureRank(
                procedure=proc.name,
                score=round(score, 2),
                writes_affected_object=writes_affected,
                reads_affected_object=reads_affected,
                relationship_to_affected_object=relationship,
                evidence_found=evidence_found or ["No direct evidence ties this procedure to the affected object."],
                historical_incidents=historical,
                error_log_support=error_support,
                job_history_support=job_support,
            )
        )
    return sorted(
        ranks,
        key=lambda item: (
            item.writes_affected_object,
            item.error_log_support,
            item.job_history_support,
            item.reads_affected_object,
            item.score,
        ),
        reverse=True,
    )


def _requested_columns(table: TableMetadata, entities: EntityExtractionResult) -> set[str]:
    if table is None:
        return set()
    concepts: set[str] = set()
    for entity in entities.entities:
        if entity.entity_type in {"possible_column", "possible_table_or_column"}:
            concepts.update(_object_terms(entity.value))
    for keyword in entities.business_keywords or []:
        concepts.update(_object_terms(keyword))
    result = set()
    for column in table.columns:
        if _object_terms(column) & concepts:
            result.add(column)
    return result


def _confirmed_facts(evidence: list[EvidenceResult], ranked_procedures: list[ProcedureRank], affected_object: str, business_key: str | None) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for confirmed facts within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    facts = [f"Affected object: {affected_object}."]
    if business_key:
        facts.append(f"Inferred business key: {business_key}.")
    for item in evidence:
        if not item.rows:
            continue
        facts.append(f"{item.purpose}: {len(item.rows)} row(s) returned.")
        if "duplicate" in item.purpose.lower():
            facts.extend(_duplicate_facts_from_rows(item.rows, affected_object))
    direct_writers = [item.procedure for item in ranked_procedures if item.writes_affected_object]
    if direct_writers:
        facts.append(f"Direct write procedure(s) for affected object: {', '.join(direct_writers[:5])}.")
    return facts


def _duplicate_facts_from_rows(rows: list[dict], affected_object: str) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate facts from rows within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    facts: list[str] = []
    for row in rows[:3]:
        parent = row.get("parent_reference") or row.get("order_number") or row.get("business_key")
        count_key = next((key for key in row if key.endswith("_count") or key == "duplicate_count"), None)
        count = row.get(count_key) if count_key else None
        statuses = row.get("child_statuses") or row.get("shipment_statuses") or row.get("statuses")
        records_key = next((key for key in row if key.endswith("_records") or key.endswith("_numbers")), None)
        records = row.get(records_key) if records_key else None
        if parent and count:
            status_text = f" with statuses {statuses}" if statuses else ""
            records_text = f" ({records})" if records else ""
            facts.append(f"{parent} has {count} matching {affected_object}{status_text}{records_text}.")
    return facts


def _inferred_findings(intent: InvestigationIntent, ranked_procedures: list[ProcedureRank], evidence: list[EvidenceResult], documents: list[RetrievedDocument]) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for inferred findings within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    findings: list[str] = []
    if ranked_procedures and ranked_procedures[0].writes_affected_object:
        support = "error-log evidence" if ranked_procedures[0].error_log_support else "procedure metadata"
        findings.append(f"Highest-ranked write path is {ranked_procedures[0].procedure} because it directly modifies the affected object and is supported by {support}.")
    elif ranked_procedures:
        findings.append("No procedure was confirmed to directly modify the affected object; procedure-related causes remain lower confidence.")
    if any(item.rows for item in evidence):
        findings.append("At least one read-only evidence query returned rows, so reasoning should prioritize observed data over metadata-only matches.")
    if documents:
        findings.append("Retrieved documents/knowledge can support business interpretation but do not override SQL evidence.")
    if intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        findings.append("Duplicate analysis is based on inferred natural/business key columns, not primary key uniqueness.")
    return findings


def _hypotheses(intent: InvestigationIntent, affected_object: str, business_key: str | None, ranked_procedures: list[ProcedureRank], evidence: list[EvidenceResult]) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for hypotheses within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    hypotheses: list[str] = []
    if ranked_procedures and ranked_procedures[0].writes_affected_object:
        support = "; ".join(ranked_procedures[0].evidence_found[:4])
        hypotheses.append(f"Direct write logic in {ranked_procedures[0].procedure} may explain the observed evidence for {affected_object}. Evidence: {support}.")
    if intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION} and business_key:
        hypotheses.append(f"Duplicate records may be caused by missing idempotency or uniqueness around business key {business_key}.")
        if ranked_procedures and ranked_procedures[0].writes_affected_object:
            hypotheses.append(f"The likely write path is {ranked_procedures[0].procedure} because it writes {affected_object}; it may lack idempotency, uniqueness, retry, or transaction guards. Retry, job, or audit evidence is still needed to fully prove the exact execution path.")
    if any(item.error for item in evidence):
        hypotheses.append("Some evidence queries failed, so missing privileges or metadata gaps may hide a stronger explanation.")
    if not hypotheses:
        hypotheses.append("Additional evidence is required before a root cause can be confirmed.")
    return hypotheses


def _self_validation(affected_object: str, ranked_procedures: list[ProcedureRank], confirmed: list[str], hypotheses: list[str]) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for self validation within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    top = ranked_procedures[0] if ranked_procedures else None
    graph_has_chosen = bool(top and (top.writes_affected_object or top.reads_affected_object))
    return [
        "What is the main problem phrase? Captured in Evidence-First Target Discovery reason.",
        f"What object is missing/duplicated/slow/failed? {affected_object}.",
        "Which terms are only possible causes? Listed in target discovery when secondary cause markers are present.",
        "Did I accidentally choose a secondary cause as the target? No if the affected object comes from the main problem phrase; review target reason.",
        f"Does the highest-ranked hypothesis explain observed evidence? {'Yes' if confirmed and hypotheses else 'Needs more evidence'}",
        f"Is another hypothesis stronger? {'No direct-write alternative ranked higher' if top and top.writes_affected_object else 'Possible; no direct write path was confirmed'}",
        f"Was the procedure that directly modifies {affected_object} investigated? {'Yes' if top and top.writes_affected_object else 'No direct modifier confirmed; continue investigation'}",
        f"Does the chosen root cause write the affected table? {'Yes' if top and top.writes_affected_object else 'No'}",
        f"Does the error log support the chosen root cause? {'Yes' if top and top.error_log_support else 'No; confidence remains lower until error-log evidence is found'}",
        f"Does the business process graph include the chosen procedure? {'Yes' if graph_has_chosen else 'No'}",
        f"Does procedure analysis match the report narrative? {'Yes' if top and top.writes_affected_object else 'No direct write narrative allowed'}",
    ]


def _duplicate_target_table(question: str, metadata: MetadataSearchResult) -> TableMetadata | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate target table within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    lowered = question.lower()
    target_terms: list[str] = []
    for pattern in (
        r"\bduplicate\s+(?:active\s+|open\s+|valid\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        r"\btwo\s+(?:active\s+|open\s+|valid\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        r"\bmultiple\s+(?:active\s+|open\s+|valid\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
    ):
        target_terms.extend(match.group(1).lower() for match in re.finditer(pattern, lowered))
    if not target_terms:
        return None
    for term in target_terms:
        normalized = term[:-1] if term.endswith("s") else term
        candidates = [
            table
            for table in metadata.tables
            if normalized in table.name.lower() or term in table.name.lower()
        ]
        if candidates:
            return sorted(candidates, key=lambda table: (table.score, len(table.name)), reverse=True)[0]
    return None


def _write_path_graph(affected_object: str, procedure_analysis: list[ProcedureAnalysis]) -> list[tuple[str, str]]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for write path graph within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    edges: list[tuple[str, str]] = []
    affected_l = affected_object.lower()
    for proc in procedure_analysis:
        # Execution order approximation: read object(s) -> procedure -> written affected object.
        for table in proc.tables_read:
            clean = _clean_identifier(table)
            if clean.lower() == affected_l:
                edges.append((clean, proc.name))
        for table in proc.tables_written:
            clean = _clean_identifier(table)
            if clean.lower() == affected_l:
                edges.append((proc.name, clean))
    return list(dict.fromkeys(edges))


def _related_tables(affected_object: str, metadata: MetadataSearchResult) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for related tables within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    related: set[str] = set()
    affected_l = affected_object.lower()
    for table in metadata.tables:
        for fk in table.foreign_keys or []:
            referred = str(fk.get("referred_table") or "")
            if table.name.lower() == affected_l and referred:
                related.add(referred.lower())
            if referred.lower() == affected_l:
                related.add(table.name.lower())
    return sorted(related)


def _tables_in_sql(sql: str) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for tables in sql within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return list(
        dict.fromkeys(
            _clean_identifier(match.group(1))
            for match in re.finditer(r"\b(?:from|join)\s+([`\"\[\]\w.]+)", sql, re.I)
        )
    )


def _duplicate_group_columns(evidence: list[EvidenceResult]) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for duplicate group columns within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    columns: list[str] = []
    for item in evidence:
        if "duplicate" not in item.purpose.lower():
            continue
        match = re.search(r"\bgroup\s+by\s+([`\"\[\]\w.]+)", item.sql, re.I)
        if match:
            columns.append(_clean_identifier(match.group(1)))
        for row in item.rows:
            for key in row:
                if key != "duplicate_count":
                    columns.append(key)
    return list(dict.fromkeys(columns))


def _error_log_supports(procedure_name: str, affected_object: str, evidence: list[EvidenceResult]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for error log supports within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    proc_l = procedure_name.lower()
    affected_terms = _object_terms(affected_object)
    for item in evidence:
        source = f"{item.purpose} {item.sql}".lower()
        if "error" not in source and "log" not in source:
            continue
        for row in item.rows:
            row_text = " ".join(str(value) for value in row.values()).lower()
            row_proc = str(row.get("procedure_name") or row.get("procedure") or "").lower()
            if (row_proc == proc_l or proc_l in row_text) and any(term in row_text or term in source for term in affected_terms):
                return True
    return False


def _job_history_supports(procedure_name: str, evidence: list[EvidenceResult]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for job history supports within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    proc_l = procedure_name.lower()
    for item in evidence:
        source = f"{item.purpose} {item.sql}".lower()
        if not any(term in source for term in ("job", "history", "batch", "run")):
            continue
        if any(proc_l in " ".join(str(value) for value in row.values()).lower() for row in item.rows):
            return True
    return False


def _object_terms(affected_object: str) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for object terms within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    lowered = affected_object.lower()
    singular = lowered[:-1] if lowered.endswith("s") else lowered
    return {lowered, singular, singular.replace("_", " "), lowered.replace("_", " ")}


def _table(metadata: MetadataSearchResult, name: str) -> TableMetadata | None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for table within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    return next((table for table in metadata.tables if table.name.lower() == name.lower()), None)


def _is_primary_key(column: str, table: TableMetadata) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for is primary key within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    return column in (table.primary_key or []) or column.lower() == "id" or column.lower().endswith("_id")


def _clean_identifier(value: Any) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for clean identifier within evidence_focus_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_focus_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    return str(value).strip("`[]\"").split(".")[-1]

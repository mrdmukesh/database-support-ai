from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult, build_deterministic_root_cause_claim
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument


UNREPRODUCED_MESSAGE = "Reported issue could not be reproduced from connected database evidence."


@dataclass(frozen=True)
class EvidenceGateCheckResult:
    check: str
    status: str
    reason: str
    inspected_objects: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CombinedEvidenceGateResult:
    status: str
    passed_checks: list[str]
    failed_checks: list[str]
    reasons: list[str]


def combine_evidence_gate_checks(
    primary_entity_result: EvidenceGateCheckResult,
    relevant_object_result: EvidenceGateCheckResult,
) -> CombinedEvidenceGateResult:
    """Combine only the primary-entity and relevant-object evidence checks."""
    results = (primary_entity_result, relevant_object_result)
    expected_checks = {"primary_entity_found", "relevant_object_inspected"}
    if {result.check for result in results} != expected_checks:
        raise ValueError("Exactly primary_entity_found and relevant_object_inspected results are required.")

    passed_checks = [result.check for result in results if result.status == "PASS"]
    failed_checks = [result.check for result in results if result.status != "PASS"]
    status = "PASS" if len(passed_checks) == 2 else "PARTIAL" if len(passed_checks) == 1 else "FAIL"
    return CombinedEvidenceGateResult(
        status=status,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        reasons=[result.reason for result in results],
    )


def relevant_object_inspected(
    object_references: list[dict[str, Any]] | None,
) -> EvidenceGateCheckResult:
    """Check whether at least one valid, relevant database object was inspected."""
    valid_types = {
        "table",
        "view",
        "stored_procedure",
        "procedure",
        "job",
        "log",
        "log_source",
    }
    valid_name = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*$")
    inspected_objects: list[str] = []
    invalid_references = 0

    for reference in object_references or []:
        if not isinstance(reference, dict):
            invalid_references += 1
            continue
        object_type = str(reference.get("object_type") or "").strip().casefold().replace(" ", "_")
        name = str(reference.get("name") or "").strip()
        if object_type not in valid_types or not valid_name.fullmatch(name):
            invalid_references += 1
            continue
        if name.casefold() not in {item.casefold() for item in inspected_objects}:
            inspected_objects.append(name)

    if inspected_objects:
        return EvidenceGateCheckResult(
            check="relevant_object_inspected",
            status="PASS",
            reason="At least one relevant object was inspected.",
            inspected_objects=inspected_objects,
        )
    reason = "No relevant object was inspected."
    if invalid_references:
        reason = "No relevant object was inspected because all supplied object references were invalid."
    return EvidenceGateCheckResult(
        check="relevant_object_inspected",
        status="FAIL",
        reason=reason,
        inspected_objects=[],
    )


def primary_entity_found(
    requested_entity: str | None,
    evidence_package: list[EvidenceResult] | None,
) -> EvidenceGateCheckResult:
    """Check whether the requested primary entity occurs in collected evidence."""
    entity = str(requested_entity or "").strip()
    if not entity:
        return EvidenceGateCheckResult(
            check="primary_entity_found",
            status="FAIL",
            reason="The requested primary entity is empty.",
        )
    if evidence_package is None:
        return EvidenceGateCheckResult(
            check="primary_entity_found",
            status="FAIL",
            reason="The evidence package is missing.",
        )

    matches = sum(
        1
        for evidence_item in evidence_package
        for row in evidence_item.rows
        for value in row.values()
        if str(value).strip().casefold() == entity.casefold()
    )
    if matches:
        return EvidenceGateCheckResult(
            check="primary_entity_found",
            status="PASS",
            reason=f"Requested primary entity '{entity}' was found in collected evidence ({matches} match(es)).",
        )
    return EvidenceGateCheckResult(
        check="primary_entity_found",
        status="FAIL",
        reason=f"Requested primary entity '{entity}' was not found in collected evidence.",
    )


@dataclass(frozen=True)
class EvidenceGateResult:
    required: bool
    reproduced: bool
    business_key_exists: bool
    reported_condition_exists: bool
    affected_rows_exist: bool
    parent_child_relationship_exists: bool
    confirmed_facts: list[str]
    blocking_reasons: list[str]
    missing_evidence: list[str]
    status_interpretation: list[str]


def run_evidence_gate(
    *,
    question: str,
    intent: InvestigationIntent,
    entities: EntityExtractionResult,
    metadata: MetadataSearchResult,
    evidence: list[EvidenceResult],
    evidence_focus: EvidenceFocus | None,
    documents: list[RetrievedDocument],
) -> EvidenceGateResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Determines whether the reported issue was reproduced from connected database evidence before root-cause
        conclusions are trusted.

    Input:
        Question, intent, extracted entities, metadata, collected evidence, evidence focus, and retrieved documents.

    Output:
        EvidenceGateResult showing whether business key, affected rows, reported condition, and relationships exist.

    Called by:
        Main /chat/ask orchestration after evidence collection and before final root-cause reasoning.

    Flow:
        Evidence Collector -> Evidence Gate -> Reasoning Engine or unreproduced-issue response.

    Safety:
        Uses already-collected read-only evidence only. It does not execute SQL or apply fixes.
    """

    required = intent in {
        InvestigationIntent.PRODUCTION_INVESTIGATION,
        InvestigationIntent.DUPLICATE_DATA,
        InvestigationIntent.MISSING_DATA,
        InvestigationIntent.PERFORMANCE_INVESTIGATION,
        InvestigationIntent.PROCESS_FLOW_BREAK,
        InvestigationIntent.FAILED_BATCH_JOB,
    }
    facts: list[str] = []
    blockers: list[str] = []
    status_notes: list[str] = []
    key_values = [
        entity.value
        for entity in entities.entities
        if entity.entity_type in {"business_key", "exact_id_or_code", "status_or_code"}
    ]
    business_key_exists = True
    if key_values:
        business_key_exists = any(_row_contains(row, value) for item in evidence for row in item.rows for value in key_values)
        if business_key_exists:
            facts.append(f"Supplied business key found in returned evidence: {', '.join(key_values[:3])}.")
        else:
            blockers.append(f"Supplied business key not found in returned rows: {', '.join(key_values[:3])}.")
    affected_rows_exist = _affected_rows_exist(evidence, evidence_focus)
    if affected_rows_exist:
        facts.append("Affected rows were returned by safe SQL evidence.")
    else:
        blockers.append("No affected rows were returned by the evidence plan.")
    relationship_exists = _relationship_exists(metadata, evidence, evidence_focus)
    if relationship_exists:
        facts.append("Parent-child relationship was confirmed by metadata or join evidence.")
    elif intent in {InvestigationIntent.PRODUCTION_INVESTIGATION, InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.MISSING_DATA, InvestigationIntent.PROCESS_FLOW_BREAK}:
        blockers.append("Parent-child relationship was not confirmed by metadata or SQL join evidence.")
    condition_exists = _reported_condition_exists(question, intent, evidence, documents, status_notes)
    if condition_exists:
        facts.append("Reported condition was reproduced by returned evidence.")
    else:
        blockers.append(_condition_blocker(intent))
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION and not _has_explain_or_row_estimate(evidence):
        condition_exists = False
        blockers.append("Performance investigation lacks EXPLAIN or row-estimate evidence.")
    if not required:
        return EvidenceGateResult(False, True, business_key_exists, True, affected_rows_exist, relationship_exists, facts, [], [], status_notes)
    relationship_ok = relationship_exists or intent in {
        InvestigationIntent.PERFORMANCE_INVESTIGATION,
        InvestigationIntent.DUPLICATE_DATA,
        InvestigationIntent.PROCESS_FLOW_BREAK,
    }
    reproduced = business_key_exists and affected_rows_exist and condition_exists and relationship_ok
    return EvidenceGateResult(
        required=required,
        reproduced=reproduced,
        business_key_exists=business_key_exists,
        reported_condition_exists=condition_exists,
        affected_rows_exist=affected_rows_exist,
        parent_child_relationship_exists=relationship_ok,
        confirmed_facts=facts,
        blocking_reasons=[] if reproduced else blockers,
        missing_evidence=[] if reproduced else blockers,
        status_interpretation=status_notes,
    )


def unreproduced_reasoning(gate: EvidenceGateResult) -> ReasoningResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles unreproduced reasoning within the Database Support AI application flow.
    
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
    claim = build_deterministic_root_cause_claim(UNREPRODUCED_MESSAGE)
    return ReasoningResult(
        summary=UNREPRODUCED_MESSAGE,
        likely_root_causes=[claim] if claim else [],
        supporting_evidence=gate.confirmed_facts or ["No confirming rows were returned for the reported issue."],
        missing_evidence=gate.missing_evidence or gate.blocking_reasons,
        recommended_fix=["No fix recommended until the reported condition is reproduced from connected database evidence."],
        test_cases=[
            {
                "Test ID": "TC-REPRO-001",
                "Scenario": "Reproduce reported issue",
                "Steps": "Run generated read-only SQL against the connected database.",
                "Expected Result": "Rows prove the supplied key, affected rows, relationship, and reported condition.",
                "Actual Result": "Not reproduced",
                "Status": "Blocked",
            }
        ],
        proof_of_fix=["No proof-of-fix SQL is valid until the issue is reproduced."],
        rollback_plan=["Do not deploy data, procedure, or schema changes while reproduction evidence is missing."],
        risks=["Fixes recommended without evidence can create new production defects."],
        confirmed_facts=gate.confirmed_facts,
        inferred_findings=[],
        hypotheses=["Investigation stopped at the evidence gate because the reported condition was not confirmed."],
        response_type="insufficient_evidence",
    )


def _affected_rows_exist(evidence: list[EvidenceResult], evidence_focus: EvidenceFocus | None) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for affected rows exist within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    if not evidence_focus or evidence_focus.affected_object == "Not determined":
        return any(item.rows for item in evidence)
    affected = evidence_focus.affected_object.lower()
    return any(item.rows and affected in f"{item.purpose} {item.sql}".lower() for item in evidence)


def _relationship_exists(metadata: MetadataSearchResult, evidence: list[EvidenceResult], evidence_focus: EvidenceFocus | None) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for relationship exists within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    if any(item.rows and " join " in f" {item.sql.lower()} " for item in evidence):
        return True
    affected = evidence_focus.affected_object.lower() if evidence_focus else ""
    if not affected:
        return bool(metadata.tables)
    for table in metadata.tables:
        for fk in table.foreign_keys or []:
            referred = str(fk.get("referred_table") or "").lower()
            if table.name.lower() == affected or referred == affected:
                return True
    return False


def _reported_condition_exists(
    question: str,
    intent: InvestigationIntent,
    evidence: list[EvidenceResult],
    documents: list[RetrievedDocument],
    status_notes: list[str],
) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for reported condition exists within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    if intent in {InvestigationIntent.DUPLICATE_DATA, InvestigationIntent.PRODUCTION_INVESTIGATION}:
        rows = [row for item in evidence if "duplicate" in item.purpose.lower() for row in item.rows]
        if not rows:
            return False
        if re.search(r"\b(active|open)\b", question, re.I):
            return any(_row_has_open_status(row, documents, status_notes) for row in rows)
        if any(_duplicate_count(row) > 1 for row in rows):
            return True
        return True
    if intent == InvestigationIntent.MISSING_DATA:
        return any(item.purpose == "Confirmed Missing Related Record Candidates" and item.rows for item in evidence)
    if intent == InvestigationIntent.PROCESS_FLOW_BREAK:
        return _status_transition_reproduced(evidence, status_notes)
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        return _has_explain_or_row_estimate(evidence)
    return any(item.rows for item in evidence)


def _duplicate_count(row: dict[str, Any]) -> int:
    for key, value in row.items():
        lowered = key.lower()
        if lowered == "duplicate_count" or lowered.endswith("_count"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _status_transition_reproduced(evidence: list[EvidenceResult], status_notes: list[str]) -> bool:
    status_rows = [
        row
        for item in evidence
        if "current status" in item.purpose.lower() or "status" in item.purpose.lower()
        for row in item.rows
    ]
    for row in status_rows:
        current = str(row.get("current_status") or row.get("status") or row.get("state") or "").strip().upper()
        reported = str(row.get("reported_stuck_status") or "").strip().upper()
        if current and reported and current == reported:
            status_notes.append(f"Confirmed current status remains {current}, matching the reported stuck status.")
            return True
        if current:
            status_notes.append(f"Confirmed current status from returned evidence: {current}.")
    return bool(status_rows)


def _row_has_open_status(row: dict[str, Any], documents: list[RetrievedDocument], status_notes: list[str]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for row has open status within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    values: list[str] = []
    for key, value in row.items():
        if "status" in key.lower() or "state" in key.lower():
            values.extend(part.strip() for part in str(value).split(",") if part.strip())
    if not values:
        status_notes.append("Duplicate evidence did not return status/state values.")
        return False
    text = " ".join(f"{doc.title} {doc.snippet}" for doc in documents).lower()
    open_labels = _extract_documented_statuses(text, ("active", "open", "pending", "incomplete"))
    closed_labels = _extract_documented_statuses(text, ("closed", "complete", "completed", "final", "cancelled", "canceled", "inactive"))
    openish_tokens = ("active", "open", "pending", "new", "ready", "created", "ordered", "scheduled", "progress", "processing", "retry", "failed")
    closedish_tokens = ("closed", "complete", "completed", "cancelled", "canceled", "void", "deleted", "archived", "final", "posted", "paid", "shipped", "resulted")
    active: list[str] = []
    for value in values:
        normalized = value.lower()
        if normalized in closed_labels:
            continue
        if normalized in open_labels or (any(token in normalized for token in openish_tokens) and not any(token in normalized for token in closedish_tokens)):
            active.append(value)
    if active:
        status_notes.append(f"Open/active status inferred from documents or status naming: {', '.join(active[:5])}.")
        return True
    status_notes.append(f"Returned statuses were not inferred as open/active: {', '.join(values[:5])}.")
    return False


def _extract_documented_statuses(text: str, markers: tuple[str, ...]) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for extract documented statuses within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Document indexing must remain workspace-scoped and must not index unapproved live database rows.
    """
    statuses: set[str] = set()
    for marker in markers:
        for match in re.finditer(rf"{marker}[^.\n:]*[:=]\s*([a-zA-Z0-9_, /\-]+)", text):
            statuses.update(part.strip().lower() for part in re.split(r"[,/ ]+", match.group(1)) if len(part.strip()) > 1)
    return statuses


def _has_explain_or_row_estimate(evidence: list[EvidenceResult]) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for has explain or row estimate within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    for item in evidence:
        text = f"{item.purpose} {item.sql}".upper()
        if "EXPLAIN" in text and (item.rows or item.error is None):
            return True
        if item.rows and any(any("rows" in str(key).lower() for key in row) for row in item.rows):
            return True
    return False


def _row_contains(row: dict[str, Any], value: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for row contains within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    needle = value.lower()
    return any(needle == str(item).lower() or needle in str(item).lower() for item in row.values())


def _condition_blocker(intent: InvestigationIntent) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for condition blocker within evidence_gate_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in evidence_gate_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Must preserve read-only investigation behavior and avoid modifying customer databases.
    """
    if intent == InvestigationIntent.DUPLICATE_DATA:
        return "Duplicate condition was not confirmed by returned rows."
    if intent == InvestigationIntent.PRODUCTION_INVESTIGATION:
        return "Production incident condition was not confirmed by returned rows."
    if intent == InvestigationIntent.MISSING_DATA:
        return "Missing related records were not confirmed by returned rows."
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        return "Performance condition was not confirmed by EXPLAIN or row-estimate evidence."
    return "Reported condition was not confirmed by returned rows."

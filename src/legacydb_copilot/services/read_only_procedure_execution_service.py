from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    build_deterministic_root_cause_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.pii_masking_service import mask_secrets_text
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
_PARAMETER = re.compile(r"^@[A-Za-z_][A-Za-z0-9_]*$")
_WRITE = re.compile(
    r"(?i)\b(insert\s+into|update\s+[\[\]\w.]|delete\s+from|merge\s+into|"
    r"select\s+.+?\s+into\s+[\[\]\w.]|create|alter|drop|truncate|grant|revoke)\b",
    re.S,
)
_FORBIDDEN = re.compile(
    r"(?i)\b(sp_executesql|xp_cmdshell|sp_oacreate|openquery|openrowset|"
    r"opendatasource|external\s+name|external\s+script|create\s+assembly|"
    r"alter\s+assembly|bulk\s+insert|bcp|clr)\b"
)
_LINKED_SERVER = re.compile(
    r"(?i)(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)"
    r"\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)"
    r"\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)"
    r"\.(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)"
)
_CALLED_ROUTINE = re.compile(r"(?i)\bexec(?:ute)?\s+(?!as\b)([\[\]\w.]+)")
_SECRET_KEY = re.compile(
    r"(?i)(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|token|connection[_-]?string)"
)


class ProcedureExecutionBlocked(ValueError):
    """Raised when a requested routine does not satisfy the read-only policy."""


@dataclass(frozen=True)
class ProcedureExecutionApproval:
    workspace_id: str
    database_name: str
    approved_workspace_ids: frozenset[str]
    approved_database_names: frozenset[str]
    timeout_seconds: int = 30
    row_limit: int = 100


def execute_approved_procedures(
    connector: Any,
    analyses: list[ProcedureAnalysis],
    *,
    explicit_procedure_names: set[str],
    known_objects: set[str],
    seed_evidence: list[EvidenceResult],
    approval: ProcedureExecutionApproval,
) -> list[EvidenceResult]:
    """Execute explicitly selected, definition-verified, read-only procedures."""
    _validate_approval(approval)
    explicit = {_normalize_identifier(item) for item in explicit_procedure_names}
    results: list[EvidenceResult] = []
    analyzed: set[str] = set()
    for index, analysis in enumerate(analyses, start=1):
        if _normalize_identifier(analysis.name) not in explicit:
            continue
        analyzed.add(_normalize_identifier(analysis.name))
        evidence_id = f"PROC-EXEC-{index}"
        started = datetime.now(UTC)
        try:
            _validate_analysis(analysis, known_objects)
            parameters = _resolve_parameters(analysis, seed_evidence)
            rows = connector.execute_read_only_procedure(
                analysis.name,
                parameters=parameters,
                timeout_seconds=approval.timeout_seconds,
                row_limit=approval.row_limit,
            )
            rows = [_sanitize_row(row) for row in list(rows)[: approval.row_limit]]
            duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            results.append(
                EvidenceResult(
                    purpose=f"Execute approved read-only procedure {analysis.name}",
                    sql="",
                    rows=rows,
                    evidence_id=evidence_id,
                    execution_status="succeeded",
                    evidence_semantics="procedure_execution",
                    supports_claim=(
                        f"The explicitly requested read-only procedure {analysis.name} "
                        "completed and returned persisted result evidence."
                    ),
                    evidence_relevance="relevant",
                    scan_policy_decision={
                        "decision": "allowed",
                        "reason": "explicit_definition_verified_read_only_procedure",
                        "procedure": analysis.name,
                        "parameters": _sanitize_parameters(parameters),
                        "timeout_seconds": approval.timeout_seconds,
                        "row_limit": approval.row_limit,
                        "duration_ms": duration_ms,
                    },
                )
            )
        except Exception as exc:
            duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            results.append(
                EvidenceResult(
                    purpose=f"Execute approved read-only procedure {analysis.name}",
                    sql="",
                    rows=[],
                    error=f"{type(exc).__name__}: {mask_secrets_text(str(exc))}",
                    evidence_id=evidence_id,
                    execution_status=(
                        "timed_out" if isinstance(exc, TimeoutError) else "blocked"
                    ),
                    evidence_semantics="execution_failure",
                    evidence_relevance="relevant",
                    scan_policy_decision={
                        "decision": "blocked",
                        "reason": type(exc).__name__,
                        "procedure": analysis.name,
                        "timeout_seconds": approval.timeout_seconds,
                        "row_limit": approval.row_limit,
                        "duration_ms": duration_ms,
                    },
                )
            )
    for missing in sorted(explicit - analyzed):
        results.append(
            EvidenceResult(
                purpose=f"Execute approved read-only procedure {missing}",
                sql="",
                rows=[],
                error="ProcedureExecutionBlocked: Procedure definition inspection is required.",
                evidence_id=f"PROC-EXEC-{len(results) + 1}",
                execution_status="blocked",
                evidence_semantics="execution_failure",
                evidence_relevance="relevant",
                scan_policy_decision={
                    "decision": "blocked",
                    "reason": "unknown_procedure",
                    "procedure": missing,
                    "timeout_seconds": approval.timeout_seconds,
                    "row_limit": approval.row_limit,
                },
            )
        )
    return results


def verified_expected_null_behavior(
    evidence: list[EvidenceResult],
    analyses: list[ProcedureAnalysis],
) -> tuple[EvidenceResult, ProcedureAnalysis] | None:
    """Recognize verified NULL-in/NULL-out behavior from execution plus definition."""
    execution = next(
        (
            item
            for item in evidence
            if item.evidence_semantics == "procedure_execution"
            and item.execution_status == "succeeded"
            and any(_null_propagation_columns(row) is not None for row in item.rows)
        ),
        None,
    )
    if execution is None:
        return None
    procedure_name = str(execution.scan_policy_decision.get("procedure") or "")
    analysis = next(
        (
            item
            for item in analyses
            if _normalize_identifier(item.name) == _normalize_identifier(procedure_name)
            and re.search(
                r"(?is)case\s+when\s+(?:\w+\.)?DateOfBirth\s+is\s+null\s+then\s+null",
                item.definition,
            )
        ),
        None,
    )
    return (execution, analysis) if analysis is not None else None


def expected_null_behavior_reasoning(
    execution: EvidenceResult,
    analysis: ProcedureAnalysis,
    evidence: list[EvidenceResult] | None = None,
) -> ReasoningResult:
    execution_row = next(
        row for row in execution.rows if _null_propagation_columns(row) is not None
    )
    source_column, result_column = _null_propagation_columns(execution_row) or ("value", "result")
    entity_value = _entity_value(execution_row)
    entity_label = f" for {entity_value}" if entity_value else ""
    conclusion = (
        f"{source_column} is NULL{entity_label}, so {result_column} cannot be calculated."
    )
    evidence_records = evidence or [execution]
    evidence_refs = list(
        dict.fromkeys(
            item.evidence_id
            for item in evidence_records
            if item.execution_status == "succeeded"
            and not item.error
            and item.evidence_relevance != "irrelevant"
            and any(
                (not entity_value or entity_value in {str(value) for value in row.values()})
                and (
                    source_column in row
                    or "exists" in item.supports_claim.casefold()
                    or item.evidence_id == execution.evidence_id
                )
                for row in item.rows
            )
        )
    )
    claim = build_deterministic_root_cause_claim(
        conclusion,
        evidence_refs,
        evidence_records,
    )
    return ReasoningResult(
        summary=(
            f"Verified read-only evidence shows the target{entity_label} exists with "
            f"{source_column} = NULL. The inspected NULL-handling in {analysis.name} therefore "
            f"returns {result_column} = NULL "
            "as expected; no stored-procedure defect was reproduced."
        ),
        likely_root_causes=[claim] if claim is not None else [],
        supporting_evidence=[
            f"The target{entity_label} exists with {source_column} = NULL.",
            (
                f"{analysis.name} explicitly returns NULL {result_column} "
                f"when {source_column} is NULL."
            ),
            f"{execution.evidence_id} preserved {source_column} = NULL and {result_column} = NULL.",
        ],
        missing_evidence=[
            f"The evidence does not establish why {source_column} is NULL."
        ],
        recommended_fix=[
            f"Verify and enter a valid {source_column} only through the approved source-data "
            f"process, then rerun the {result_column} calculation; do not perform a direct "
            "database update from this investigation."
        ],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=["Inferring an age or changing procedure behavior would create unsupported data."],
        confirmed_facts=[conclusion],
        inferred_findings=[],
        hypotheses=[],
        response_type="confirmed_root_cause",
    )


def _null_propagation_columns(row: dict[str, Any]) -> tuple[str, str] | None:
    """Infer a NULL source/result pair from typed procedure output, without entity fixtures."""
    null_columns = [name for name, value in row.items() if value is None]
    if len(null_columns) < 2:
        return None
    source = next(
        (name for name in null_columns if name.casefold() in {"dateofbirth", "date_of_birth"}),
        null_columns[0],
    )
    result = next((name for name in null_columns if name != source), None)
    return (source, result) if result else None


def _entity_value(row: dict[str, Any]) -> str:
    for name, value in row.items():
        normalized = name.casefold().replace("_", "")
        if value is not None and normalized.endswith(("number", "key", "code", "id")):
            return str(value)
    return ""


def _validate_approval(approval: ProcedureExecutionApproval) -> None:
    if approval.workspace_id not in approval.approved_workspace_ids:
        raise ProcedureExecutionBlocked("Workspace is not approved for procedure execution.")
    approved_databases = {item.casefold() for item in approval.approved_database_names}
    if approval.database_name.casefold() not in approved_databases:
        raise ProcedureExecutionBlocked("Database is not approved for procedure execution.")
    if not 1 <= approval.timeout_seconds <= 30:
        raise ProcedureExecutionBlocked("Procedure timeout must be between 1 and 30 seconds.")
    if not 1 <= approval.row_limit <= 100:
        raise ProcedureExecutionBlocked("Procedure row limit must be between 1 and 100.")


def _validate_analysis(analysis: ProcedureAnalysis, known_objects: set[str]) -> None:
    if not _IDENTIFIER.fullmatch(analysis.name):
        raise ProcedureExecutionBlocked("Procedure identifier is invalid.")
    if not analysis.definition_available or not analysis.definition.strip():
        raise ProcedureExecutionBlocked("Procedure definition inspection is required.")
    if analysis.object_type != "STORED_PROCEDURE":
        raise ProcedureExecutionBlocked("Requested object is not a stored procedure.")
    body = re.split(r"\bAS\b", analysis.definition, maxsplit=1, flags=re.I)[-1]
    if analysis.tables_written or any(
        (
            analysis.insert_statements,
            analysis.update_statements,
            analysis.delete_statements,
            analysis.merge_statements,
        )
    ) or _WRITE.search(body):
        raise ProcedureExecutionBlocked("Procedure definition contains write operations.")
    if analysis.dynamic_sql or _CALLED_ROUTINE.search(body):
        raise ProcedureExecutionBlocked("Dynamic SQL or nested procedure calls are not allowed.")
    if _FORBIDDEN.search(body) or _LINKED_SERVER.search(body):
        raise ProcedureExecutionBlocked(
            "Procedure uses a forbidden external or privileged feature."
        )
    known = {_normalize_identifier(item) for item in known_objects}
    unknown = [
        item for item in analysis.tables_read if _normalize_identifier(item) not in known
    ]
    if unknown:
        raise ProcedureExecutionBlocked("Procedure has unknown dependencies.")


def _resolve_parameters(
    analysis: ProcedureAnalysis,
    evidence: list[EvidenceResult],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    rows = [row for item in evidence if item.execution_status == "succeeded" for row in item.rows]
    for parameter in analysis.input_parameters:
        if not _PARAMETER.fullmatch(parameter):
            raise ProcedureExecutionBlocked("Procedure parameter name is invalid.")
        wanted = parameter.lstrip("@").casefold()
        match = next(
            (
                value
                for row in rows
                for key, value in row.items()
                if key.casefold() == wanted and _safe_parameter_value(value)
            ),
            None,
        )
        if match is None:
            raise ProcedureExecutionBlocked(
                f"No verified evidence resolved required parameter {parameter}."
            )
        values[parameter] = match
    return values


def _safe_parameter_value(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): (
            "[MASKED_SECRET]"
            if _SECRET_KEY.search(str(key))
            else mask_secrets_text(value) if isinstance(value, str) else value
        )
        for key, value in row.items()
    }


def _sanitize_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "[MASKED_SECRET]" if _SECRET_KEY.search(key) else value
        for key, value in parameters.items()
    }


def _normalize_identifier(value: str) -> str:
    return value.replace("[", "").replace("]", "").casefold()

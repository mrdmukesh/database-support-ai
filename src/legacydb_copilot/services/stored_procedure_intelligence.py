from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcedureAnalysis:
    name: str
    definition_available: bool
    tables_read: list[str]
    tables_written: list[str]
    joins: int
    insert_statements: int
    update_statements: int
    delete_statements: int
    merge_statements: int
    loops: int
    transactions: int
    try_catch: bool
    rollback_statements: int
    cursors: int
    temp_tables: int
    dynamic_sql: bool
    missing_exists_checks: bool
    missing_uniqueness_checks: bool
    deadlock_risk: str
    locking_risk: str
    complexity_score: int
    complexity: str
    business_rules: list[str]
    definition_excerpt: str


def _read_definition(connector, procedure_name: str) -> str:
    return connector.get_procedure_definition(procedure_name)


def _identifiers(pattern: str, definition: str) -> list[str]:
    return list(dict.fromkeys(match.group(1).strip("`[]\"") for match in re.finditer(pattern, definition, re.I)))


def analyze_stored_procedures(connector, procedure_names: list[str]) -> list[ProcedureAnalysis]:
    analyses: list[ProcedureAnalysis] = []
    for procedure_name in procedure_names[:8]:
        try:
            definition = _read_definition(connector, procedure_name)
        except Exception:
            definition = ""
        lowered = definition.lower()
        tables_read = _identifiers(r"\bfrom\s+([`\"\[\]\w.]+)", definition)
        tables_read.extend(_identifiers(r"\bjoin\s+([`\"\[\]\w.]+)", definition))
        tables_read = list(dict.fromkeys(tables_read))
        tables_written = []
        insert_statements = len(re.findall(r"\binsert\s+into\b", lowered))
        update_statements = len(re.findall(r"\bupdate\s+[`\"\[\]\w.]+", lowered))
        delete_statements = len(re.findall(r"\bdelete\s+from\b", lowered))
        merge_statements = len(re.findall(r"\bmerge\s+into\b", lowered))
        for pattern in (
            r"\binsert\s+into\s+([`\"\[\]\w.]+)",
            r"\bupdate\s+([`\"\[\]\w.]+)",
            r"\bdelete\s+from\s+([`\"\[\]\w.]+)",
            r"\bmerge\s+into\s+([`\"\[\]\w.]+)",
        ):
            tables_written.extend(_identifiers(pattern, definition))
        tables_written = list(dict.fromkeys(tables_written))
        joins = len(re.findall(r"\bjoin\b", lowered))
        loops = len(re.findall(r"\b(loop|while|cursor\s+for)\b", lowered))
        transactions = len(re.findall(r"\b(begin\s+transaction|start\s+transaction|commit|rollback)\b", lowered))
        try_catch = bool(re.search(r"\btry\b|\bcatch\b|exception\s+when", lowered))
        rollback_statements = len(re.findall(r"\brollback\b", lowered))
        cursors = len(re.findall(r"\bcursor\b", lowered))
        temp_tables = len(re.findall(r"(#\w+|temporary\s+table|temp\s+table)", lowered))
        dynamic_sql = bool(re.search(r"\b(exec|execute|sp_executesql|prepare|concat\s*\()", lowered))
        has_write = bool(tables_written)
        missing_exists_checks = has_write and not bool(re.search(r"\bexists\b", lowered))
        missing_uniqueness_checks = has_write and not bool(re.search(r"\b(unique|duplicate|count\s*\(|group\s+by|exists)\b", lowered))
        complexity_score = (
            joins
            + loops * 2
            + transactions
            + cursors * 2
            + temp_tables
            + insert_statements
            + update_statements
            + delete_statements
            + merge_statements * 2
            + (2 if dynamic_sql else 0)
        )
        complexity = "High" if complexity_score >= 8 else "Medium" if complexity_score >= 3 else "Low"
        locking_risk = "High" if transactions and tables_written else "Medium" if tables_written else "Low"
        deadlock_risk = "High" if transactions and len(tables_written) > 1 else "Medium" if transactions or cursors else "Low"
        rules = []
        for line in definition.splitlines():
            stripped = line.strip()
            if re.search(r"\b(if|case|where|having)\b", stripped, re.I):
                rules.append(stripped[:220])
            if len(rules) >= 8:
                break
        analyses.append(
            ProcedureAnalysis(
                name=procedure_name,
                definition_available=bool(definition),
                tables_read=tables_read,
                tables_written=tables_written,
                joins=joins,
                insert_statements=insert_statements,
                update_statements=update_statements,
                delete_statements=delete_statements,
                merge_statements=merge_statements,
                loops=loops,
                transactions=transactions,
                try_catch=try_catch,
                rollback_statements=rollback_statements,
                cursors=cursors,
                temp_tables=temp_tables,
                dynamic_sql=dynamic_sql,
                missing_exists_checks=missing_exists_checks,
                missing_uniqueness_checks=missing_uniqueness_checks,
                deadlock_risk=deadlock_risk,
                locking_risk=locking_risk,
                complexity_score=complexity_score,
                complexity=complexity,
                business_rules=rules,
                definition_excerpt=definition[:2000],
            )
        )
    return analyses

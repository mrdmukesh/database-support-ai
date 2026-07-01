from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class CorrelatedEvidence:
    evidence_type: str
    subject: str
    finding: str
    support: str
    confidence: str


def correlate_evidence(
    *,
    evidence: list[EvidenceResult],
    procedure_analysis: list[ProcedureAnalysis],
    documents: list[RetrievedDocument],
) -> list[CorrelatedEvidence]:
    correlated: list[CorrelatedEvidence] = []
    for item in evidence:
        if item.error:
            correlated.append(CorrelatedEvidence("SQL", item.purpose, item.error, item.sql, "Low"))
        elif item.rows:
            correlated.append(
                CorrelatedEvidence(
                    "SQL",
                    item.purpose,
                    f"{len(item.rows)} row(s) returned",
                    _sample_row(item.rows),
                    "High",
                )
            )
        else:
            correlated.append(CorrelatedEvidence("SQL", item.purpose, "No rows returned", item.sql, "Medium"))
    for proc in procedure_analysis:
        if not proc.definition_available:
            correlated.append(CorrelatedEvidence("Procedure", proc.name, "Procedure definition was not available from metadata privileges", "Metadata only", "Low"))
            continue
        finding = (
            f"Reads {len(proc.tables_read)} table(s), writes {len(proc.tables_written)} table(s), "
            f"complexity {proc.complexity}, locking risk {proc.locking_risk}"
        )
        support = "; ".join(
            [
                f"Reads: {', '.join(proc.tables_read) or 'none detected'}",
                f"Writes: {', '.join(proc.tables_written) or 'none detected'}",
                f"joins={proc.joins}",
                f"loops={proc.loops}",
                f"transactions={proc.transactions}",
                f"dynamic_sql={proc.dynamic_sql}",
            ]
        )
        correlated.append(CorrelatedEvidence("Procedure", proc.name, finding, support, "High"))
    for doc in documents[:5]:
        correlated.append(CorrelatedEvidence("Document", doc.title, "Retrieved as supporting documentation", doc.snippet or "Document title matched question context", "Medium"))
    return correlated


def _sample_row(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    row = rows[0]
    return "; ".join(f"{key}={value}" for key, value in list(row.items())[:8])

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from legacydb_copilot.services.report_generator import (
    ExecutiveSummary,
    InvestigationReport,
    ReportCover,
    ReportSection,
    ReportSqlBlock,
    ReportTable,
)


def report_to_dict(report: InvestigationReport) -> dict[str, Any]:
    return asdict(report)


def report_from_dict(data: dict[str, Any]) -> InvestigationReport:
    return InvestigationReport(
        cover=ReportCover(**data["cover"]),
        executive_summary=ExecutiveSummary(**data["executive_summary"]),
        sections=[_section_from_dict(item) for item in data.get("sections", [])],
        confidential_watermark=bool(data.get("confidential_watermark", True)),
    )


def _section_from_dict(data: dict[str, Any]) -> ReportSection:
    return ReportSection(
        title=data["title"],
        paragraphs=list(data.get("paragraphs", [])),
        items=list(data.get("items", [])),
        tables=[ReportTable(**item) for item in data.get("tables", [])],
        sql_blocks=[ReportSqlBlock(**item) for item in data.get("sql_blocks", [])],
    )

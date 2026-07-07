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
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles report to dict within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    return asdict(report)


def report_from_dict(data: dict[str, Any]) -> InvestigationReport:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles report from dict within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    return InvestigationReport(
        cover=ReportCover(**data["cover"]),
        executive_summary=ExecutiveSummary(**data["executive_summary"]),
        sections=[_section_from_dict(item) for item in data.get("sections", [])],
        confidential_watermark=bool(data.get("confidential_watermark", True)),
    )


def _section_from_dict(data: dict[str, Any]) -> ReportSection:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for section from dict within report_snapshot_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_snapshot_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    return ReportSection(
        title=data["title"],
        paragraphs=list(data.get("paragraphs", [])),
        items=list(data.get("items", [])),
        tables=[ReportTable(**item) for item in data.get("tables", [])],
        sql_blocks=[ReportSqlBlock(**item) for item in data.get("sql_blocks", [])],
    )

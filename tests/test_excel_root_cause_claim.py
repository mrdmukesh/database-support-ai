from pathlib import Path

from openpyxl import load_workbook

from legacydb_copilot.agents.reasoning_agent import RootCauseClaim, RootCauseSupportStatus
from legacydb_copilot.services.excel_generator import write_xlsx
from legacydb_copilot.services.report_generator import (
    ExecutiveSummary,
    InvestigationReport,
    ReportCover,
    ReportSection,
    ReportTable,
)


def test_excel_serializes_structured_root_cause_claim(tmp_path: Path) -> None:
    claim = RootCauseClaim(
        conclusion="The retry procedure may cause duplicate claims.",
        evidence_refs=["SQL-1", "PROC-2"],
        status=RootCauseSupportStatus.PARTIALLY_SUPPORTED,
    )
    report = InvestigationReport(
        cover=ReportCover("Report", "Workspace", "Database", "AI", "Now", "INV-1", "1"),
        executive_summary=ExecutiveSummary(
            "Duplicate claim",
            "APT-2005 has duplicate claims.",
            "Medium",
            "Duplicate processing",
            75,
            claim,  # type: ignore[arg-type] - regression input from the dynamic report path
            "Review retry behavior",
            "Complete",
        ),
        sections=[
            ReportSection(
                title="Root Cause",
                tables=[ReportTable("Claims", ["Claim"], [{"Claim": claim}])],
            )
        ],
    )
    output_path = tmp_path / "report.xlsx"

    write_xlsx(report, output_path)

    workbook = load_workbook(output_path)
    summary_values = [cell.value for cell in workbook["Executive Summary"]["B"]]
    assert str(claim) in summary_values
    assert workbook["Claims"]["A2"].value == str(claim)

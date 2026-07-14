from datetime import datetime

from legacydb_copilot.services.pdf_generator import write_pdf
from legacydb_copilot.services.report_generator import (
    ExecutiveSummary,
    InvestigationReport,
    ReportCover,
    ReportSection,
    ReportTable,
)


def test_pdf_table_splits_an_oversized_evidence_row(tmp_path) -> None:
    report = InvestigationReport(
        cover=ReportCover(
            title="Enterprise Investigation Report",
            workspace="test",
            database="test",
            generated_by="test",
            generated_on=datetime.now().isoformat(),
            investigation_id="test-id",
            report_version="1.0",
        ),
        executive_summary=ExecutiveSummary(
            issue_title="test",
            issue_description="test",
            severity="low",
            business_impact="none",
            confidence_score=50,
            estimated_root_cause="test",
            recommendation_summary="test",
            status="draft",
        ),
        sections=[
            ReportSection(
                title="Evidence",
                tables=[
                    ReportTable(
                        title="Long evidence",
                        columns=["procedure_name", "query", "result", "notes"],
                        rows=[
                            {
                                "procedure_name": "retry_activity_entries",
                                "query": "SELECT <value> & details\n" * 150,
                                "result": "duplicate activity entry " * 200,
                                "notes": "evidence " * 200,
                            }
                        ],
                    )
                ],
            )
        ],
    )

    output = tmp_path / "long-evidence.pdf"
    write_pdf(report, output)

    assert output.exists()
    assert output.stat().st_size > 0

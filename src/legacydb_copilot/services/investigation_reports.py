from __future__ import annotations

from legacydb_copilot.services.docx_generator import write_docx
from legacydb_copilot.services.excel_generator import write_xlsx
from legacydb_copilot.services.pdf_generator import write_pdf
from legacydb_copilot.services.report_generator import (
    GeneratedReport,
    InvestigationReport,
    report_file_stem,
    report_output_dir,
    write_html,
)


def generate_investigation_report_files(report: InvestigationReport) -> GeneratedReport:
    output_dir = report_output_dir(report.cover.investigation_id)
    file_stem = report_file_stem(report)
    html_path = output_dir / f"{file_stem}.html"
    pdf_path = output_dir / f"{file_stem}.pdf"
    docx_path = output_dir / f"{file_stem}.docx"
    xlsx_path = output_dir / f"{file_stem}.xlsx"

    write_html(report, html_path)
    write_pdf(report, pdf_path)
    write_docx(report, docx_path)
    write_xlsx(report, xlsx_path)

    return GeneratedReport(
        investigation_id=report.cover.investigation_id,
        directory=output_dir,
        html_path=html_path,
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

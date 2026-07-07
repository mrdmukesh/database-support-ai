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
from legacydb_copilot.services.storage_service import get_app_storage


_REPORT_CONTENT_TYPES = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def generate_investigation_report_files(report: InvestigationReport) -> GeneratedReport:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles generate investigation report files within the Database Support AI application flow.
    
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

    storage = get_app_storage()
    for path in (html_path, pdf_path, docx_path, xlsx_path):
        storage.save_bytes(
            path.as_posix(),
            path.read_bytes(),
            _REPORT_CONTENT_TYPES.get(path.suffix.lower()),
        )

    return GeneratedReport(
        investigation_id=report.cover.investigation_id,
        directory=output_dir,
        html_path=html_path,
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
    )

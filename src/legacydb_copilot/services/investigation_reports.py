from __future__ import annotations

from dataclasses import replace

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


def report_storage_references(generated: GeneratedReport) -> dict[str, str]:
    """Return the exact persisted object key for every generated artifact."""
    return {
        path.name: path.as_posix()
        for path in (
            generated.html_path,
            generated.pdf_path,
            generated.docx_path,
            generated.xlsx_path,
            generated.audit_html_path,
            generated.audit_pdf_path,
            generated.audit_docx_path,
            generated.audit_xlsx_path,
        )
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
    executive_report = _executive_report(report)
    html_path = output_dir / f"{file_stem}_executive_rca.html"
    pdf_path = output_dir / f"{file_stem}_executive_rca.pdf"
    docx_path = output_dir / f"{file_stem}_executive_rca.docx"
    xlsx_path = output_dir / f"{file_stem}_executive_rca.xlsx"
    audit_html_path = output_dir / f"{file_stem}_full_audit.html"
    audit_pdf_path = output_dir / f"{file_stem}_full_audit.pdf"
    audit_docx_path = output_dir / f"{file_stem}_full_audit.docx"
    audit_xlsx_path = output_dir / f"{file_stem}_full_audit.xlsx"

    write_html(executive_report, html_path)
    write_pdf(executive_report, pdf_path)
    write_docx(executive_report, docx_path)
    write_xlsx(executive_report, xlsx_path)
    write_html(report, audit_html_path)
    write_pdf(report, audit_pdf_path)
    write_docx(report, audit_docx_path)
    write_xlsx(report, audit_xlsx_path)

    generated = GeneratedReport(
        investigation_id=report.cover.investigation_id,
        directory=output_dir,
        html_path=html_path,
        pdf_path=pdf_path,
        docx_path=docx_path,
        xlsx_path=xlsx_path,
        audit_html_path=audit_html_path,
        audit_pdf_path=audit_pdf_path,
        audit_docx_path=audit_docx_path,
        audit_xlsx_path=audit_xlsx_path,
    )
    storage = get_app_storage()
    try:
        for filename, storage_key in report_storage_references(generated).items():
            path = output_dir / filename
            storage.save_bytes(storage_key, path.read_bytes(), _REPORT_CONTENT_TYPES.get(path.suffix.lower()))
    except Exception as exc:
        raise RuntimeError(f"Report persistence failed: {exc}") from exc
    return generated


def _executive_report(report: InvestigationReport) -> InvestigationReport:
    priority_titles = [
        "Executive Summary",
        "Question",
        "AI Status",
        "Key Findings",
        "Top Evidence",
        "Procedure Path",
        "Root Cause",
        "Fix",
        "Tests",
        "Rollback",
    ]
    selected = []
    seen_titles: set[str] = set()
    for title in priority_titles:
        section = next((item for item in report.sections if item.title == title and item.title not in seen_titles), None)
        if section is not None:
            selected.append(section)
            seen_titles.add(section.title)
    if not selected:
        selected = report.sections[:6]
    return replace(
        report,
        cover=replace(report.cover, title=f"Executive RCA Report - {report.cover.title}"),
        sections=selected,
    )

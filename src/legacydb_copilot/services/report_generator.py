from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from legacydb_copilot.common import Environment as AppEnvironment
from legacydb_copilot.config import Settings


@dataclass(frozen=True)
class ReportTable:
    title: str
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class ReportSqlBlock:
    purpose: str
    expected_result: str
    risk: str
    sql: str


@dataclass(frozen=True)
class ReportSection:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)
    sql_blocks: list[ReportSqlBlock] = field(default_factory=list)


@dataclass(frozen=True)
class ReportCover:
    title: str
    workspace: str
    database: str
    generated_by: str
    generated_on: str
    investigation_id: str
    report_version: str


@dataclass(frozen=True)
class ExecutiveSummary:
    issue_title: str
    issue_description: str
    severity: str
    business_impact: str
    confidence_score: int
    estimated_root_cause: str
    recommendation_summary: str
    status: str


@dataclass(frozen=True)
class InvestigationReport:
    cover: ReportCover
    executive_summary: ExecutiveSummary
    sections: list[ReportSection]
    confidential_watermark: bool = True


@dataclass(frozen=True)
class GeneratedReport:
    investigation_id: str
    directory: Path
    html_path: Path
    pdf_path: Path
    docx_path: Path
    xlsx_path: Path
    audit_html_path: Path | None = None
    audit_pdf_path: Path | None = None
    audit_docx_path: Path | None = None
    audit_xlsx_path: Path | None = None

    def links(self) -> dict[str, str]:
        """
        Owner: Mukesh Dabi
        Purpose:
            Handles links within the Database Support AI application flow.
        
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
        base = f"/reports/{self.investigation_id}"
        links = {
            "investigation_id": self.investigation_id,
            "mode": "executive_rca",
            "html": f"{base}/{self.html_path.name}",
            "pdf": f"{base}/{self.pdf_path.name}",
            "docx": f"{base}/{self.docx_path.name}",
            "xlsx": f"{base}/{self.xlsx_path.name}",
            "audit_html": f"{base}/{self.audit_html_path.name}" if self.audit_html_path else f"{base}/{self.html_path.name}",
            "audit_pdf": f"{base}/{self.audit_pdf_path.name}" if self.audit_pdf_path else f"{base}/{self.pdf_path.name}",
            "audit_docx": f"{base}/{self.audit_docx_path.name}" if self.audit_docx_path else f"{base}/{self.docx_path.name}",
            "audit_xlsx": f"{base}/{self.audit_xlsx_path.name}" if self.audit_xlsx_path else f"{base}/{self.xlsx_path.name}",
        }
        settings = Settings.from_env()
        if settings.ai_debug_trace_enabled and settings.environment != AppEnvironment.PRODUCTION:
            links["ai_trace"] = f"{base}/ai-debug-trace"
        return links


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "reports" / "templates"
REPORT_HISTORY_DIR = Path("reports/history")
REPORT_VERSION = "1.0"


def now_label() -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles now label within the Database Support AI application flow.
    
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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_investigation_id() -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles new investigation id within the Database Support AI application flow.
    
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
    return f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8].upper()}"


def report_output_dir(investigation_id: str) -> Path:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles report output dir within the Database Support AI application flow.
    
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
    path = REPORT_HISTORY_DIR / investigation_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_file_stem(report: InvestigationReport) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles report file stem within the Database Support AI application flow.
    
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
    title = report.executive_summary.issue_title or report.cover.title
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)[:70].strip("_") or "investigation_report"
    return f"{slug}_{report.cover.investigation_id}"


def render_html(report: InvestigationReport) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles render html within the Database Support AI application flow.
    
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
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("investigation_report.html")
    return template.render(report=report)


def write_html(report: InvestigationReport, output_path: Path) -> None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles write html within the Database Support AI application flow.
    
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
    output_path.write_text(render_html(report), encoding="utf-8")


def rows_to_table(title: str, rows: list[dict[str, Any]], preferred_columns: list[str]) -> ReportTable:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles rows to table within the Database Support AI application flow.
    
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
    columns = [column for column in preferred_columns if any(column in row for row in rows)]
    if not columns and rows:
        columns = list(rows[0].keys())
    return ReportTable(title=title, columns=columns or preferred_columns, rows=rows)

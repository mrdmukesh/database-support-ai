from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape


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

    def links(self) -> dict[str, str]:
        base = f"/reports/{self.investigation_id}"
        return {
            "investigation_id": self.investigation_id,
            "html": f"{base}/{self.html_path.name}",
            "pdf": f"{base}/{self.pdf_path.name}",
            "docx": f"{base}/{self.docx_path.name}",
            "xlsx": f"{base}/{self.xlsx_path.name}",
        }


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "reports" / "templates"
REPORT_HISTORY_DIR = Path("reports/history")
REPORT_VERSION = "1.0"


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_investigation_id() -> str:
    return f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8].upper()}"


def report_output_dir(investigation_id: str) -> Path:
    path = REPORT_HISTORY_DIR / investigation_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_file_stem(report: InvestigationReport) -> str:
    title = report.executive_summary.issue_title or report.cover.title
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)[:70].strip("_") or "investigation_report"
    return f"{slug}_{report.cover.investigation_id}"


def render_html(report: InvestigationReport) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("investigation_report.html")
    return template.render(report=report)


def write_html(report: InvestigationReport, output_path: Path) -> None:
    output_path.write_text(render_html(report), encoding="utf-8")


def rows_to_table(title: str, rows: list[dict[str, Any]], preferred_columns: list[str]) -> ReportTable:
    columns = [column for column in preferred_columns if any(column in row for row in rows)]
    if not columns and rows:
        columns = list(rows[0].keys())
    return ReportTable(title=title, columns=columns or preferred_columns, rows=rows)

param(
    [string]$ProjectRoot = "D:\AI_Code\LegacyDB Support Copilot",
    [string]$OutputPath = ".\research\results\combined-benchmark-dashboard.html",
    [switch]$IncludeInvalid,
    [switch]$OpenReport
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputPath))
$OutputDirectory = Split-Path $OutputPath -Parent
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$GeneratorPath = Join-Path $OutputDirectory "_generate_combined_dashboard.py"

$PythonCode = @'
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

from evaluation.cli.__main__ import build_store
from evaluation.framework.models import EvaluationScenarioExecutionModel

output_path = Path(sys.argv[1])
include_invalid = sys.argv[2].lower() == "true"


def parse_json(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def first(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def num(value):
    try:
        return float(value)
    except Exception:
        return None


def bool_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() == "true"


session = build_store().session_factory()
records = []
try:
    executions = (
        session.query(EvaluationScenarioExecutionModel)
        .order_by(EvaluationScenarioExecutionModel.created_at.asc())
        .all()
    )

    for execution in executions:
        result = parse_json(getattr(execution, "result_json", None))
        validation = parse_json(
            getattr(execution, "evaluation_json", None)
            or getattr(execution, "validation_json", None)
        )
        judge = parse_json(
            getattr(execution, "judge_json", None)
            or getattr(execution, "ai_judge_json", None)
        )

        scenario_id = getattr(execution, "scenario_id", None)
        if not scenario_id:
            continue

        row_status = getattr(execution, "status", None)
        if row_status == "invalid_configuration" and not include_invalid:
            continue

        primary = judge.get("primary") or {}
        human_review = judge.get("human_review") or {}

        records.append({
            "scenario_id": scenario_id,
            "domain": scenario_id.split("-")[0].lower(),
            "result_id": first(getattr(execution, "id", None), getattr(execution, "execution_id", None)),
            "run_id": first(getattr(execution, "evaluation_run_id", None), getattr(execution, "run_id", None), result.get("run_id")),
            "investigation_id": first(result.get("investigation_id"), getattr(execution, "investigation_id", None)),
            "created_at": str(getattr(execution, "created_at", "") or ""),
            "row_status": row_status,
            "investigation_status": first(result.get("investigation_status"), result.get("status")),
            "canonical_entity": first(result.get("canonical_investigated_entity"), validation.get("canonical_investigated_entity")),
            "benchmark_validity": first(validation.get("benchmark_validity"), result.get("benchmark_validity"), getattr(execution, "benchmark_validity", None)),
            "deterministic_score": num(first(validation.get("final_score"), validation.get("deterministic_score"), result.get("deterministic_score"), getattr(execution, "deterministic_score", None))),
            "classification": first(validation.get("classification"), result.get("classification"), getattr(execution, "classification", None)),
            "ai_judge_score": num(first(primary.get("weighted_score"), judge.get("weighted_score"), judge.get("overall_score"), result.get("ai_judge_score"), getattr(execution, "ai_judge_score", None))),
            "human_review_required": bool_value(first(human_review.get("required"), judge.get("human_review_required"), result.get("human_review_required"), getattr(execution, "human_review_required", None))),
            "latency_seconds": num(first(result.get("latency_seconds"), getattr(execution, "latency_seconds", None))),
            "failure": first(validation.get("failure"), result.get("failure"), getattr(execution, "failure", None)),
        })
finally:
    session.close()

# Latest persisted execution per scenario.
latest = {}
for record in records:
    latest[record["scenario_id"]] = record
records = list(latest.values())

domain_order = {"banking": 1, "orders": 2, "shipping": 3, "payroll": 4, "clinic": 5}
records.sort(key=lambda r: (domain_order.get(r["domain"], 99), r["scenario_id"]))

valid = [r for r in records if str(r.get("benchmark_validity", "")).lower() == "valid" and r.get("deterministic_score") is not None]
scored = [r for r in valid if r.get("ai_judge_score") is not None]
passed = [r for r in valid if str(r.get("classification", "")).lower() == "pass"]
review = [r for r in records if r.get("human_review_required") is True]


def avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def fmt(value):
    return "—" if value is None else f"{value:.2f}"


by_domain = defaultdict(list)
for row in records:
    by_domain[row["domain"]].append(row)

domain_cards = []
for domain in sorted(by_domain, key=lambda d: domain_order.get(d, 99)):
    rows = by_domain[domain]
    dvalid = [r for r in rows if str(r.get("benchmark_validity", "")).lower() == "valid" and r.get("deterministic_score") is not None]
    dscored = [r for r in dvalid if r.get("ai_judge_score") is not None]
    dpasses = [r for r in dvalid if str(r.get("classification", "")).lower() == "pass"]
    dhuman = [r for r in rows if r.get("human_review_required") is True]
    domain_cards.append(f'''<div class="card domain-card">
      <h3>{html.escape(domain.title())}</h3>
      <div class="mini-grid">
        <div><span>Scenarios</span><strong>{len(rows)}</strong></div>
        <div><span>Valid</span><strong>{len(dvalid)}</strong></div>
        <div><span>Passes</span><strong>{len(dpasses)}</strong></div>
        <div><span>Avg deterministic</span><strong>{fmt(avg([r["deterministic_score"] for r in dvalid]))}</strong></div>
        <div><span>Avg AI Judge</span><strong>{fmt(avg([r["ai_judge_score"] for r in dscored]))}</strong></div>
        <div><span>Human review</span><strong>{len(dhuman)}</strong></div>
      </div>
    </div>''')


def status_badge(row):
    if row.get("row_status") == "invalid_configuration":
        return '<span class="badge bad">INVALID CONFIG</span>'
    cls = str(row.get("classification") or "").lower()
    if cls == "pass":
        return '<span class="badge good">PASS</span>'
    if cls:
        return f'<span class="badge warn">{html.escape(cls.upper())}</span>'
    status = row.get("investigation_status") or row.get("row_status") or "PENDING"
    return f'<span class="badge neutral">{html.escape(str(status))}</span>'


table_rows = []
chart_rows = []
for row in records:
    run_id = row.get("run_id")
    report = "—"
    if run_id:
        relative = (Path("research") / "results" / str(run_id) / "research-report.html").as_posix()
        report = f'<a href="{html.escape(relative)}">Open report</a>'

    table_rows.append(f'''<tr>
      <td>{html.escape(row["domain"].title())}</td>
      <td><code>{html.escape(row["scenario_id"])}</code></td>
      <td>{html.escape(str(row.get("canonical_entity") or "—"))}</td>
      <td>{status_badge(row)}</td>
      <td>{fmt(row.get("deterministic_score"))}</td>
      <td>{fmt(row.get("ai_judge_score"))}</td>
      <td>{"Yes" if row.get("human_review_required") else "No"}</td>
      <td>{fmt(row.get("latency_seconds"))}</td>
      <td>{html.escape(str(row.get("investigation_id") or "—"))}</td>
      <td>{report}</td>
    </tr>''')

    det = max(0, min(100, row.get("deterministic_score") or 0))
    judge = max(0, min(100, row.get("ai_judge_score") or 0))
    chart_rows.append(f'''<div class="bar-row">
      <div class="bar-label" title="{html.escape(row["scenario_id"])}">{html.escape(row["scenario_id"])}</div>
      <div class="track"><div class="fill det" style="width:{det}%"></div></div><div>{fmt(row.get("deterministic_score"))}</div>
      <div class="track"><div class="fill judge" style="width:{judge}%"></div></div><div>{fmt(row.get("ai_judge_score"))}</div>
    </div>''')

html_doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Combined Benchmark Dashboard</title>
<style>
:root{{--bg:#0f172a;--panel:#111827;--panel2:#1f2937;--text:#e5e7eb;--muted:#94a3b8;--line:#334155;--accent:#38bdf8;--purple:#a78bfa;--good:#22c55e;--warn:#f59e0b;--bad:#ef4444}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#0f172a,#111827);color:var(--text);font-family:Segoe UI,Arial,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:28px}}h1{{margin:0}}.sub{{color:var(--muted);margin:7px 0 22px}}.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}}.card,.panel{{background:rgba(17,24,39,.95);border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 26px rgba(0,0,0,.18)}}.kpi{{padding:15px}}.kpi span,.mini-grid span{{display:block;color:var(--muted);font-size:12px}}.kpi strong{{display:block;font-size:26px;margin-top:5px}}.domains{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}}.domain-card{{padding:15px}}.domain-card h3{{margin:0 0 10px}}.mini-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.mini-grid strong{{font-size:18px}}.panel{{padding:17px;margin-bottom:18px;overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:1120px}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}}th{{color:#cbd5e1;background:#111827;position:sticky;top:0}}tr:hover{{background:rgba(56,189,248,.05)}}.badge{{display:inline-block;padding:4px 8px;border-radius:999px;font-size:11px;font-weight:700}}.good{{background:rgba(34,197,94,.15);color:#86efac}}.warn{{background:rgba(245,158,11,.15);color:#fcd34d}}.bad{{background:rgba(239,68,68,.15);color:#fca5a5}}.neutral{{background:rgba(148,163,184,.15);color:#cbd5e1}}a{{color:var(--accent);text-decoration:none}}.bar-row{{display:grid;grid-template-columns:220px 1fr 58px 1fr 58px;gap:9px;align-items:center;margin:8px 0}}.bar-label{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px}}.track{{height:12px;border-radius:999px;background:#0b1220;border:1px solid #22304a;overflow:hidden}}.fill{{height:100%}}.det{{background:var(--accent)}}.judge{{background:var(--purple)}}.note{{color:var(--muted);font-size:12px}}@media(max-width:1100px){{.kpis{{grid-template-columns:repeat(3,1fr)}}.domains{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><div class="wrap">
<h1>Database Support AI — Combined Benchmark Dashboard</h1>
<div class="sub">Latest persisted result for each scenario</div>
<section class="kpis">
<div class="card kpi"><span>Scenarios</span><strong>{len(records)}</strong></div>
<div class="card kpi"><span>Valid scored</span><strong>{len(valid)}</strong></div>
<div class="card kpi"><span>Passes</span><strong>{len(passed)}</strong></div>
<div class="card kpi"><span>Avg deterministic</span><strong>{fmt(avg([r["deterministic_score"] for r in valid]))}</strong></div>
<div class="card kpi"><span>Avg AI Judge</span><strong>{fmt(avg([r["ai_judge_score"] for r in scored]))}</strong></div>
<div class="card kpi"><span>Human review</span><strong>{len(review)}</strong></div>
</section>
<section class="domains">{''.join(domain_cards)}</section>
<section class="panel"><h2>Score comparison</h2>{''.join(chart_rows)}<p class="note">Blue = deterministic; purple = AI Judge.</p></section>
<section class="panel"><h2>Detailed results</h2><table><thead><tr><th>Domain</th><th>Scenario</th><th>Entity</th><th>Status</th><th>Deterministic</th><th>AI Judge</th><th>Human review</th><th>Latency</th><th>Investigation</th><th>Report</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></section>
<section class="panel"><p class="note">Invalid-configuration rows are {'included' if include_invalid else 'excluded'}. Use -IncludeInvalid to show them.</p></section>
</div></body></html>'''

output_path.write_text(html_doc, encoding="utf-8")
print(json.dumps({
    "output_path": str(output_path),
    "scenarios": len(records),
    "valid_scored": len(valid),
    "passes": len(passed),
    "average_deterministic": avg([r["deterministic_score"] for r in valid]),
    "average_ai_judge": avg([r["ai_judge_score"] for r in scored]),
    "human_review": len(review),
}, indent=2))
'@

Set-Content -Path $GeneratorPath -Value $PythonCode -Encoding UTF8

$IncludeInvalidValue = if ($IncludeInvalid) { "true" } else { "false" }

$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $ProjectRoot

try {
    & $Python $GeneratorPath $OutputPath $IncludeInvalidValue

    if ($LASTEXITCODE -ne 0) {
        throw "Combined dashboard generation failed."
    }
}
finally {
    if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $PreviousPythonPath
    }
}

Remove-Item $GeneratorPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Combined dashboard created:" -ForegroundColor Green
Write-Host $OutputPath

if ($OpenReport) {
    Start-Process $OutputPath
}
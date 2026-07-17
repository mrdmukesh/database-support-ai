param(
    [string]$ProjectRoot = "D:\AI_Code\LegacyDB Support Copilot",
    [string]$OutputDirectory = ".\research\results\five-domain-recovered",
    [switch]$SkipValidation,
    [switch]$SkipJudge
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Python executable not found: $Python" }

$OutputDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputDirectory))
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$Results = @(
    @{ Domain="banking"; ScenarioId="banking-pilot-001"; ResultId="529c4d1c-3fc0-4c4b-97a2-d5ac2961ed36" },
    @{ Domain="orders";  ScenarioId="orders-pilot-001";  ResultId="7a858b3c-3456-4136-9480-84443f424a5e" },
    @{ Domain="payroll"; ScenarioId="payroll-pilot-001"; ResultId="629db61a-b55b-4ef5-a5b4-10ee0db8a7fd" },
    @{ Domain="clinic";  ScenarioId="clinic-pilot-001";  ResultId="9d0cf446-3d9d-4f64-b1de-28fdf26f0dc0" }
)
$ShippingRunId = "ef9a60c2-08f7-44f1-b3cc-2d50d300a5f5"

function Invoke-EvalCommand {
    param([string[]]$Arguments,[string]$LogName)
    $LogPath = Join-Path $OutputDirectory $LogName
    Write-Host "`nRunning: python $($Arguments -join ' ')" -ForegroundColor Cyan
    & $Python @Arguments *>&1 | Tee-Object -FilePath $LogPath
    if ($LASTEXITCODE -ne 0) { throw "Command failed. See $LogPath" }
}

Write-Host "Recovering and scoring existing five-domain results." -ForegroundColor Green
Write-Host "No investigations will be rerun."

if (-not $SkipValidation) {
    foreach ($Item in $Results) {
        Invoke-EvalCommand @("-m","evaluation.cli","validate-result","--result-id",$Item.ResultId) "$($Item.Domain)-validate.log"
    }
}

if (-not $SkipJudge) {
    foreach ($Item in $Results) {
        Invoke-EvalCommand @("-m","evaluation.cli","judge-result","--result-id",$Item.ResultId) "$($Item.Domain)-judge.log"
    }
}

$ShippingJson = Join-Path $ProjectRoot "research\results\$ShippingRunId\results.json"
if (-not (Test-Path $ShippingJson)) {
    Invoke-EvalCommand @("-m","evaluation.cli","report","--run-id",$ShippingRunId) "shipping-report.log"
}

$Extractor = Join-Path $OutputDirectory "_extract_results.py"
@'
import csv, json, sys
from pathlib import Path
from evaluation.cli.__main__ import build_store
from evaluation.framework.models import EvaluationScenarioExecutionModel

project_root = Path(sys.argv[1]); output_dir = Path(sys.argv[2]); shipping_run_id = sys.argv[3]
items = [
 ("banking","banking-pilot-001","529c4d1c-3fc0-4c4b-97a2-d5ac2961ed36"),
 ("orders","orders-pilot-001","7a858b3c-3456-4136-9480-84443f424a5e"),
 ("payroll","payroll-pilot-001","629db61a-b55b-4ef5-a5b4-10ee0db8a7fd"),
 ("clinic","clinic-pilot-001","9d0cf446-3d9d-4f64-b1de-28fdf26f0dc0"),
]

def parse(v):
    if isinstance(v, dict): return v
    if not v: return {}
    try: return json.loads(v)
    except Exception: return {}

def attr(row,*names):
    for n in names:
        if hasattr(row,n):
            v=getattr(row,n)
            if v is not None: return v
    return None

def first(*vals):
    for v in vals:
        if v not in (None,""): return v
    return None

rows=[]
session=build_store().session_factory()
try:
    for domain,scenario_id,result_id in items:
        row=session.get(EvaluationScenarioExecutionModel,result_id)
        if row is None:
            rows.append(dict(domain=domain,scenario_id=scenario_id,result_id=result_id,run_id=None,investigation_id=None,investigation_status="NOT_FOUND",canonical_entity=None,benchmark_validity="invalid",deterministic_score=None,classification=None,ai_judge_score=None,human_review_required=None,latency_seconds=None,input_tokens=None,output_tokens=None,failure="Result row not found",source="evaluation_database"))
            continue
        result=parse(attr(row,"result_json")); evaluation=parse(attr(row,"evaluation_json","validation_json")); judge=parse(attr(row,"judge_json","ai_judge_json"))
        rows.append(dict(
            domain=domain,
            scenario_id=first(attr(row,"scenario_id"),scenario_id),
            result_id=result_id,
            run_id=first(attr(row,"evaluation_run_id","run_id"),result.get("run_id")),
            investigation_id=first(result.get("investigation_id"),attr(row,"investigation_id")),
            investigation_status=first(result.get("investigation_status"),result.get("status"),attr(row,"status")),
            canonical_entity=first(result.get("canonical_investigated_entity"),evaluation.get("canonical_investigated_entity")),
            benchmark_validity=first(evaluation.get("benchmark_validity"),result.get("benchmark_validity"),attr(row,"benchmark_validity")),
            deterministic_score=first(evaluation.get("deterministic_score"),result.get("deterministic_score"),attr(row,"deterministic_score")),
            classification=first(evaluation.get("classification"),result.get("classification"),attr(row,"classification")),
            ai_judge_score=first(judge.get("overall_score"),judge.get("ai_judge_score"),result.get("ai_judge_score"),attr(row,"ai_judge_score")),
            human_review_required=first(judge.get("human_review_required"),result.get("human_review_required"),attr(row,"human_review_required")),
            latency_seconds=first(result.get("latency_seconds"),attr(row,"latency_seconds")),
            input_tokens=first(result.get("input_tokens"),attr(row,"input_tokens")),
            output_tokens=first(result.get("output_tokens"),attr(row,"output_tokens")),
            failure=first(evaluation.get("failure"),result.get("failure"),attr(row,"failure")),
            source="evaluation_database"
        ))
finally:
    session.close()

shipping_path=project_root/"research"/"results"/shipping_run_id/"results.json"
if shipping_path.exists():
    payload=json.loads(shipping_path.read_text(encoding="utf-8")); s=(payload.get("scenarios") or [{}])[0]
    rows.append(dict(domain=s.get("domain","shipping"),scenario_id=s.get("scenario_id","shipping-pilot-001"),result_id=None,run_id=shipping_run_id,investigation_id=s.get("investigation_id"),investigation_status=s.get("investigation_status") or s.get("status"),canonical_entity=s.get("canonical_investigated_entity"),benchmark_validity=s.get("benchmark_validity"),deterministic_score=s.get("deterministic_score"),classification=s.get("classification"),ai_judge_score=s.get("ai_judge_score"),human_review_required=s.get("human_review_required"),latency_seconds=s.get("latency_seconds"),input_tokens=s.get("input_tokens"),output_tokens=s.get("output_tokens"),failure=s.get("failure"),source="shipping_results_json"))

order={"banking":1,"orders":2,"shipping":3,"payroll":4,"clinic":5}; rows.sort(key=lambda r:order.get(r["domain"],99))
fields=list(rows[0].keys())
with (output_dir/"five-domain-pilot-results.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
(output_dir/"five-domain-pilot-results.json").write_text(json.dumps(rows,indent=2,default=str),encoding="utf-8")

det=[float(r["deterministic_score"]) for r in rows if r["deterministic_score"] is not None]
judge=[float(r["ai_judge_score"]) for r in rows if r["ai_judge_score"] is not None]
passes=[r for r in rows if str(r.get("classification","")).lower()=="pass"]
reviews=sum(1 for r in rows if str(r.get("human_review_required","")).lower()=="true")
avg_det=sum(det)/len(det) if det else None; avg_judge=sum(judge)/len(judge) if judge else None
safe=(len(rows)==5 and len(det)==5 and len(judge)==5 and len(passes)>=4 and avg_det>=75 and avg_judge>=75 and reviews<=1 and all(str(r.get("benchmark_validity","")).lower()=="valid" for r in rows))

lines=["# Five-Domain Pilot Summary","","Generated from existing persisted results. No investigation was rerun.","","| Domain | Scenario | Status | Entity | Deterministic | AI Judge | Classification | Human Review |","|---|---|---|---|---:|---:|---|---|"]
for r in rows:
    lines.append(f"| {r['domain']} | {r['scenario_id']} | {r.get('investigation_status') or ''} | {r.get('canonical_entity') or ''} | {r.get('deterministic_score') if r.get('deterministic_score') is not None else ''} | {r.get('ai_judge_score') if r.get('ai_judge_score') is not None else ''} | {r.get('classification') or ''} | {r.get('human_review_required') if r.get('human_review_required') is not None else ''} |")
lines += ["","## Gate Summary","",f"- Scored results: {len(det)}/5",f"- Passing results: {len(passes)}/5",f"- Average deterministic score: {avg_det:.3f}" if avg_det is not None else "- Average deterministic score: unavailable",f"- Average AI Judge score: {avg_judge:.3f}" if avg_judge is not None else "- Average AI Judge score: unavailable",f"- Human review: {reviews}/5",f"- Safe for 25-scenario validation: {'YES' if safe else 'NO'}"]
(output_dir/"five-domain-pilot-summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps(dict(scenario_count=len(rows),scored_count=len(det),pass_count=len(passes),average_deterministic_score=avg_det,average_ai_judge_score=avg_judge,human_review_count=reviews,safe_for_25_scenarios=safe,output=str(output_dir)),indent=2))
'@ | Set-Content -Path $Extractor -Encoding UTF8

& $Python $Extractor $ProjectRoot $OutputDirectory $ShippingRunId *>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory "summary-generation.log")
if ($LASTEXITCODE -ne 0) { throw "Summary generation failed." }
Remove-Item $Extractor -Force -ErrorAction SilentlyContinue

Write-Host "`nCompleted." -ForegroundColor Green
Write-Host "Summary: $(Join-Path $OutputDirectory 'five-domain-pilot-summary.md')"
Write-Host "CSV:     $(Join-Path $OutputDirectory 'five-domain-pilot-results.csv')"
Write-Host "JSON:    $(Join-Path $OutputDirectory 'five-domain-pilot-results.json')"

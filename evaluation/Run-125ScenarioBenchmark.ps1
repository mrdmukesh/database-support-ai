param(
    [string]$ProjectRoot = "D:\AI_Code\LegacyDB Support Copilot",
    [string]$OutputDirectory = ".\research\results\benchmark-100-no-payroll",
    [string]$ScenarioListPath = "",
    [int]$TimeoutSeconds = 600,
    [switch]$Resume,
    [switch]$SkipPilotGate,
    [switch]$SkipJudge,
    [switch]$StopOnApplicationFailure
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $ProjectRoot
. (Join-Path $ProjectRoot "evaluation\Resolve-ScenarioInventory.ps1")

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

if (-not (Test-Path ".env.evaluation")) {
    throw ".env.evaluation was not found in $ProjectRoot"
}

$OutputDirectory = [System.IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot $OutputDirectory)
)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$MasterLog       = Join-Path $OutputDirectory "benchmark-console.log"
$ProgressCsv     = Join-Path $OutputDirectory "benchmark-progress.csv"
$SummaryJson     = Join-Path $OutputDirectory "benchmark-summary.json"
$SummaryMd       = Join-Path $OutputDirectory "benchmark-summary.md"
$DetailJson      = Join-Path $OutputDirectory "benchmark-results-detail.json"
$ScenarioListJson = Join-Path $OutputDirectory "scenario-list.json"

function Write-Log {
    param(
        [Parameter(Mandatory)][string]$Message,
        [string]$Level = "INFO"
    )

    $line = "{0:u} [{1}] {2}" -f (Get-Date), $Level, $Message
    Write-Host $line
    Add-Content -Path $MasterLog -Value $line
}

function Invoke-Python {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments,

        [Parameter(Mandatory)]
        [string]$LogFile,

        [switch]$AllowFailure
    )

    Write-Log "python $($Arguments -join ' ')"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $outputLines = @(
            & $Python @Arguments 2>&1 |
                ForEach-Object {
                    [string]$_
                }
        )

        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    foreach ($line in $outputLines) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line
    }

    $result = [PSCustomObject]@{
        ExitCode = [int]$exitCode
        Output   = ($outputLines -join [Environment]::NewLine)
    }

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "Python command failed with exit code $exitCode. See $LogFile"
    }

    return ,$result
}
function ConvertFrom-CommandJson {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Context
    )

    $start = $Text.IndexOf("{")
    $end = $Text.LastIndexOf("}")

    if ($start -lt 0 -or $end -le $start) {
        throw "No JSON object found in $Context output."
    }

    $jsonText = $Text.Substring($start, $end - $start + 1)

    try {
        return $jsonText | ConvertFrom-Json
    }
    catch {
        throw "Could not parse JSON from $Context output: $($_.Exception.Message)"
    }
}

function Get-LatestResult {
    param(
        [Parameter(Mandatory)][string]$ScenarioId
    )

    $helper = @'
import json
import sys

from evaluation.cli.__main__ import build_store
from evaluation.framework.models import EvaluationScenarioExecutionModel

scenario_id = sys.argv[1]
session = build_store().session_factory()

def parse_json(value, fallback=None):
    fallback = {} if fallback is None else fallback
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback

def first_value(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None

try:
    row = (
        session.query(EvaluationScenarioExecutionModel)
        .filter(EvaluationScenarioExecutionModel.scenario_id == scenario_id)
        .order_by(EvaluationScenarioExecutionModel.created_at.desc())
        .first()
    )

    if row is None:
        print(json.dumps({
            "found": False,
            "scenario_id": scenario_id
        }))
        raise SystemExit(0)

    result = parse_json(getattr(row, "result_json", None))
    raw_response = parse_json(getattr(row, "raw_response_json", None))
    investigation = raw_response.get("investigation", {}) if isinstance(raw_response, dict) else {}
    trace = investigation.get("debug_trace", {}) if isinstance(investigation, dict) else {}
    trace = trace if isinstance(trace, dict) else {}
    raw_errors = getattr(row, "errors_json", None)
    errors = parse_json(raw_errors, None)
    if isinstance(errors, list):
        failure = "; ".join(str(item) for item in errors if item not in (None, ""))
    elif raw_errors not in (None, "", "[]"):
        failure = "Unable to parse persisted errors_json"
    else:
        failure = first_value(result.get("failure"), result.get("errors"))

    payload = {
        "found": True,
        "result_id": first_value(
            getattr(row, "id", None),
            getattr(row, "execution_id", None),
        ),
        "run_id": first_value(
            getattr(row, "evaluation_run_id", None),
            getattr(row, "run_id", None),
            result.get("run_id"),
        ),
        "scenario_id": getattr(row, "scenario_id", scenario_id),
        "row_status": getattr(row, "status", None),
        "created_at": str(getattr(row, "created_at", "")),
        "investigation_id": first_value(
            result.get("investigation_id"),
            getattr(row, "investigation_id", None),
        ),
        "investigation_status": first_value(
            getattr(row, "investigation_status", None),
            result.get("investigation_status"),
            result.get("status"),
        ),
        "canonical_entity": result.get("canonical_investigated_entity"),
        "failure": failure,
        "ai_invoked": trace.get("ai_reasoning_invoked"),
        "ai_outcome": trace.get("ai_outcome"),
        "ai_skip_reason": trace.get("ai_skip_reason"),
        "ai_diagnostic_category": result.get("ai_diagnostic_category"),
        "llm_model_name": trace.get("llm_model_name") or trace.get("model_requested"),
        "prompt_version": trace.get("prompt_version"),
        "input_tokens": trace.get("input_tokens"),
        "output_tokens": trace.get("output_tokens"),
    }

    print(json.dumps(payload))
finally:
    session.close()
'@

    $jsonLines = @($helper | & $Python - $ScenarioId)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to retrieve latest result for $ScenarioId"
    }

    $jsonText = ($jsonLines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    return ConvertFrom-CommandJson -Text $jsonText -Context "latest-result lookup for $ScenarioId"
}

function Save-ProgressRow {
    param(
        [Parameter(Mandatory)][psobject]$Row
    )

    function Optional-Value([string]$Name) {
        $property = $Row.PSObject.Properties[$Name]
        if ($null -ne $property) { return $property.Value }
        return $null
    }

    $record = [PSCustomObject]@{
        Timestamp           = (Get-Date).ToString("s")
        Domain              = $Row.Domain
        ScenarioId          = $Row.ScenarioId
        ResultId            = $Row.ResultId
        RunId               = $Row.RunId
        InvestigationId     = $Row.InvestigationId
        RowStatus           = $Row.RowStatus
        InvestigationStatus = $Row.InvestigationStatus
        CanonicalEntity     = $Row.CanonicalEntity
        BenchmarkValidity   = $Row.BenchmarkValidity
        DeterministicScore  = $Row.DeterministicScore
        Classification      = $Row.Classification
        AIJudgeScore        = $Row.AIJudgeScore
        HumanReviewRequired = $Row.HumanReviewRequired
        Failure             = $Row.Failure
        AIInvoked           = Optional-Value "AIInvoked"
        AIOutcome           = Optional-Value "AIOutcome"
        AISkipReason        = Optional-Value "AISkipReason"
        AIDiagnosticCategory = Optional-Value "AIDiagnosticCategory"
        LLMModelName        = Optional-Value "LLMModelName"
        PromptVersion       = Optional-Value "PromptVersion"
        InputTokens         = Optional-Value "InputTokens"
        OutputTokens        = Optional-Value "OutputTokens"
    }

    if (Test-Path $ProgressCsv) {
        $record | Export-Csv -Path $ProgressCsv -NoTypeInformation -Append
    }
    else {
        $record | Export-Csv -Path $ProgressCsv -NoTypeInformation
    }
}

Write-Log "Starting guarded benchmark orchestration."
Write-Log "Output directory: $OutputDirectory"

# -------------------------------------------------------------------------
# 1. Dynamic fixture gate
# -------------------------------------------------------------------------
$auditLog = Join-Path $OutputDirectory "fixture-audit.log"

$auditCommand = Invoke-Python `
    -Arguments @("scripts\evaluation\audit_sqlserver_fixtures.py", "--dynamic") `
    -LogFile $auditLog

$auditText = Get-Content -Path $auditLog -Raw

$totalGate   = $auditText -match '"total_scenarios"\s*:\s*125'
$dynamicGate = $auditText -match '"dynamic"\s*:\s*true'
$validGate   = $auditText -match '"valid_fixtures"\s*:\s*125'
$invalidGate = $auditText -match '"invalid_fixtures"\s*:\s*0'

if (-not ($totalGate -and $dynamicGate -and $validGate -and $invalidGate)) {
    throw "Dynamic fixture gate failed. Expected total=125, dynamic=true, valid=125, invalid=0. See $auditLog"
}

Write-Log "Dynamic fixture gate passed: 125/125 valid." "PASS"

# -------------------------------------------------------------------------
# 2. Build or load the exact scenario inventory
# -------------------------------------------------------------------------
if (-not [string]::IsNullOrWhiteSpace($ScenarioListPath)) {
    $resolvedScenarioList = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $ScenarioListPath))
    if (-not (Test-Path $resolvedScenarioList)) {
        throw "Scenario list was not found: $resolvedScenarioList"
    }
    $selectedManifest = Get-Content $resolvedScenarioList -Raw | ConvertFrom-Json
    if ($null -eq $selectedManifest -or $null -eq $selectedManifest.PSObject.Properties['scenarios']) {
        throw "Validation suite manifest must be a JSON object containing a 'scenarios' array."
    }
    $selectedIds = @($selectedManifest.scenarios)
    if ($selectedIds.Count -lt 20 -or $selectedIds.Count -gt 25) {
        throw "A validation scenario list must contain 20 to 25 scenario IDs; found $($selectedIds.Count)."
    }
    if (@($selectedIds | Sort-Object -Unique).Count -ne $selectedIds.Count) {
        throw "The validation scenario list contains duplicate scenario IDs."
    }
    $scenarioRows = foreach ($scenarioId in $selectedIds) {
        $parts = [string]$scenarioId -split '-', 2
        if ($parts.Count -ne 2) { throw "Invalid scenario ID: $scenarioId" }
        $scenarioFile = Join-Path $ProjectRoot "evaluation_scenarios\$($parts[0])\$scenarioId\scenario.json"
        if (-not (Test-Path $scenarioFile)) { throw "Scenario manifest was not found: $scenarioFile" }
        $scenarioDefinition = Get-Content $scenarioFile -Raw | ConvertFrom-Json
        if (-not $scenarioDefinition.active) { throw "Inactive scenario selected: $scenarioId" }
        [PSCustomObject]@{ domain = [string]$scenarioDefinition.domain; scenario_id = [string]$scenarioDefinition.scenario_id }
    }
    $scenarioJson = $scenarioRows | ConvertTo-Json
}
else {
$scenarioHelper = @'
import json
from collections import defaultdict
from evaluation.cli.__main__ import all_scenarios

domains = ["banking", "orders", "shipping", "clinic"]
grouped = defaultdict(list)

for scenario in all_scenarios():
    grouped[scenario.domain.lower()].append(scenario.scenario_id)

output = []
for domain in domains:
    ids = sorted(grouped[domain])
    if len(ids) != 25:
        raise SystemExit(f"{domain}: expected 25 scenarios, found {len(ids)}")
    for scenario_id in ids:
        output.append({
            "domain": domain,
            "scenario_id": scenario_id
        })

if len(output) != 100:
    raise SystemExit(f"Expected 100 total scenarios, found {len(output)}")

if any(item["domain"] == "payroll" for item in output):
    raise SystemExit("Payroll scenarios were unexpectedly included.")

print(json.dumps(output, indent=2))
'@

$scenarioLines = @($scenarioHelper | & $Python -)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to build the 100-scenario list."
}

$scenarioJson = ($scenarioLines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
}
$scenarioJson | Set-Content -Path $ScenarioListJson -Encoding UTF8
$parsedScenarios = $scenarioJson | ConvertFrom-Json
$Scenarios = @(ConvertTo-ValidatedScenarioInventory -InputObject $parsedScenarios)
$ScenarioCount = $Scenarios.Count
$IncludedDomains = @(Get-ScenarioInventoryDomains -Scenarios $Scenarios)

Write-Log "Scenario inventory confirmed: $ScenarioCount scenarios across $($IncludedDomains.Count) domains ($($IncludedDomains -join ', '))." "PASS"

# -------------------------------------------------------------------------
# 3. Four-domain pilot gate (Payroll intentionally excluded)
# -------------------------------------------------------------------------
if (-not $SkipPilotGate) {
    $PilotResults = @(
        [PSCustomObject]@{
            ScenarioId = "banking-pilot-001"
            ResultId   = "529c4d1c-3fc0-4c4b-97a2-d5ac2961ed36"
        },
        [PSCustomObject]@{
            ScenarioId = "orders-pilot-001"
            ResultId   = "7a858b3c-3456-4136-9480-84443f424a5e"
        },
        [PSCustomObject]@{
            ScenarioId = "shipping-pilot-001"
            ResultId   = "5aad8d6e-7c1a-47fb-aac1-a61f2e79ff39"
        },
        [PSCustomObject]@{
            ScenarioId = "clinic-pilot-001"
            ResultId   = "9d0cf446-3d9d-4f64-b1de-28fdf26f0dc0"
        }
    )

    if ($PilotResults.Count -ne 4) {
        throw "Expected exactly 4 pilot results after excluding Payroll."
    }

    foreach ($Pilot in $PilotResults) {
        $pilotLog = Join-Path $OutputDirectory "$($Pilot.ScenarioId)-pilot-validation.log"

        Write-Log "Checking pilot result $($Pilot.ScenarioId)"

        $validationCommand = Invoke-Python `
            -Arguments @(
                "-m", "evaluation.cli",
                "validate-result",
                "--result-id", $Pilot.ResultId
            ) `
            -LogFile $pilotLog `
            -AllowFailure

        if ($validationCommand.ExitCode -ne 0) {
            throw "Pilot gate failed for $($Pilot.ScenarioId). See $pilotLog"
        }

        $pilotValidation = ConvertFrom-CommandJson `
            -Text $validationCommand.Output `
            -Context "pilot validation for $($Pilot.ScenarioId)"

        if ($pilotValidation.benchmark_validity -ne "valid") {
            throw "Pilot gate failed: $($Pilot.ScenarioId) is not benchmark-valid."
        }

        if ($null -eq $pilotValidation.final_score) {
            throw "Pilot gate failed: $($Pilot.ScenarioId) has no deterministic score."
        }

        if ($pilotValidation.critical_failure_details.Count -gt 0) {
            throw "Pilot gate failed: $($Pilot.ScenarioId) has a critical failure."
        }

        Write-Log (
            "Pilot validation passed: {0}; score={1}" -f
            $Pilot.ScenarioId,
            $pilotValidation.final_score
        ) "PASS"
    }

    Write-Log "Four-domain deterministic pilot gate passed." "PASS"
}
else {
    Write-Log "WARNING: Pilot gate was explicitly bypassed." "WARN"
}

# -------------------------------------------------------------------------
# 4. Resume support
# -------------------------------------------------------------------------
$completedScenarios = @{}

if ($Resume -and (Test-Path $ProgressCsv)) {
    Import-Csv $ProgressCsv | ForEach-Object {
        # Any scenario already recorded in the progress file is considered processed.
        # This prevents invalid/error scenarios from being retried repeatedly during Resume.
        if (-not [string]::IsNullOrWhiteSpace($_.ScenarioId)) {
            $completedScenarios[$_.ScenarioId] = $true
        }
    }

    Write-Log "Resume enabled. Found $($completedScenarios.Count) previously processed scenarios."
}

# -------------------------------------------------------------------------
# 5. Run, validate and judge all scenarios
# -------------------------------------------------------------------------
$index = 0

foreach ($Scenario in $Scenarios) {
    $index++

    $scenarioId = [string]$Scenario.scenario_id
    $domain = [string]$Scenario.domain

    if ($completedScenarios.ContainsKey($scenarioId)) {
        Write-Log "[$index/$ScenarioCount] Skipping completed scenario $scenarioId"
        continue
    }

    Write-Log "[$index/$ScenarioCount] Running $scenarioId ($domain)"

    $runLog = Join-Path $OutputDirectory "$scenarioId-run.log"

    $runCommand = Invoke-Python `
        -Arguments @(
            "-m", "evaluation.cli",
            "run-scenario",
            "--scenario-id", $scenarioId,
            "--timeout", [string]$TimeoutSeconds
        ) `
        -LogFile $runLog `
        -AllowFailure

    # Always try to inspect the persisted result, even when the CLI exits non-zero.
    # Some invalid-configuration scenarios are persisted before the command returns failure.
    $latest = $null
    try {
        $latest = Get-LatestResult -ScenarioId $scenarioId
    }
    catch {
        Write-Log ("Unable to inspect persisted result for {0}: {1}" -f $scenarioId, $_.Exception.Message) "WARN"
    }

    if ($null -eq $latest -or -not $latest.found) {
        $failureMessage = if ($runCommand.ExitCode -ne 0) {
            "Scenario execution command failed with exit code $($runCommand.ExitCode). See $runLog"
        }
        else {
            "No persisted result was found after scenario execution."
        }

        Save-ProgressRow -Row ([PSCustomObject]@{
            Domain              = $domain
            ScenarioId          = $scenarioId
            ResultId            = $null
            RunId               = $null
            InvestigationId     = $null
            RowStatus           = "execution_error"
            InvestigationStatus = "NOT_FOUND"
            CanonicalEntity     = $null
            BenchmarkValidity   = "invalid"
            DeterministicScore  = $null
            Classification      = "skipped_execution_error"
            AIJudgeScore        = $null
            HumanReviewRequired = $true
            Failure             = $failureMessage
        })

        Write-Log "[$index/$ScenarioCount] $scenarioId could not produce a persisted result. Recorded and continuing." "WARN"
        continue
    }

    if ($latest.row_status -eq "invalid_configuration") {
        Save-ProgressRow -Row ([PSCustomObject]@{
            Domain              = $domain
            ScenarioId          = $scenarioId
            ResultId            = $latest.result_id
            RunId               = $latest.run_id
            InvestigationId     = $latest.investigation_id
            RowStatus           = $latest.row_status
            InvestigationStatus = $latest.investigation_status
            CanonicalEntity     = $latest.canonical_entity
            BenchmarkValidity   = "invalid"
            DeterministicScore  = $null
            Classification      = "skipped_invalid_configuration"
            AIJudgeScore        = $null
            HumanReviewRequired = $true
            Failure             = $latest.failure
            AIInvoked           = $latest.ai_invoked
            AIOutcome           = $latest.ai_outcome
            AISkipReason        = $latest.ai_skip_reason
            AIDiagnosticCategory = $latest.ai_diagnostic_category
            LLMModelName        = $latest.llm_model_name
            PromptVersion       = $latest.prompt_version
            InputTokens         = $latest.input_tokens
            OutputTokens        = $latest.output_tokens
        })

        Write-Log "[$index/$ScenarioCount] $scenarioId produced invalid_configuration. Recorded and continuing." "WARN"
        continue
    }

    if ([string]::IsNullOrWhiteSpace([string]$latest.canonical_entity)) {
        Save-ProgressRow -Row ([PSCustomObject]@{
            Domain              = $domain
            ScenarioId          = $scenarioId
            ResultId            = $latest.result_id
            RunId               = $latest.run_id
            InvestigationId     = $latest.investigation_id
            RowStatus           = $latest.row_status
            InvestigationStatus = $latest.investigation_status
            CanonicalEntity     = $null
            BenchmarkValidity   = "invalid"
            DeterministicScore  = $null
            Classification      = "skipped_missing_canonical_entity"
            AIJudgeScore        = $null
            HumanReviewRequired = $true
            Failure             = "No canonical entity was produced."
        })

        Write-Log "[$index/$ScenarioCount] $scenarioId has no canonical entity. Recorded and continuing." "WARN"
        continue
    }

    if ($runCommand.ExitCode -ne 0) {
        Write-Log "[$index/$ScenarioCount] $scenarioId returned exit code $($runCommand.ExitCode), but a persisted result exists. Continuing to validation." "WARN"
    }

    # Deterministic validation
    $validateLog = Join-Path $OutputDirectory "$scenarioId-validate.log"

    $validationCommand = Invoke-Python `
        -Arguments @(
            "-m", "evaluation.cli",
            "validate-result",
            "--result-id", [string]$latest.result_id
        ) `
        -LogFile $validateLog `
        -AllowFailure

    if ($validationCommand.ExitCode -ne 0) {
        Save-ProgressRow -Row ([PSCustomObject]@{
            Domain              = $domain
            ScenarioId          = $scenarioId
            ResultId            = $latest.result_id
            RunId               = $latest.run_id
            InvestigationId     = $latest.investigation_id
            RowStatus           = $latest.row_status
            InvestigationStatus = $latest.investigation_status
            CanonicalEntity     = $latest.canonical_entity
            BenchmarkValidity   = "invalid"
            DeterministicScore  = $null
            Classification      = "skipped_validation_error"
            AIJudgeScore        = $null
            HumanReviewRequired = $true
            Failure             = "Deterministic validation failed. See $validateLog"
        })

        Write-Log "[$index/$ScenarioCount] Validation failed for $scenarioId. Recorded and continuing." "WARN"
        continue
    }

    try {
        $validation = ConvertFrom-CommandJson `
            -Text $validationCommand.Output `
            -Context "validation for $scenarioId"
    }
    catch {
        Save-ProgressRow -Row ([PSCustomObject]@{
            Domain              = $domain
            ScenarioId          = $scenarioId
            ResultId            = $latest.result_id
            RunId               = $latest.run_id
            InvestigationId     = $latest.investigation_id
            RowStatus           = $latest.row_status
            InvestigationStatus = $latest.investigation_status
            CanonicalEntity     = $latest.canonical_entity
            BenchmarkValidity   = "invalid"
            DeterministicScore  = $null
            Classification      = "skipped_validation_parse_error"
            AIJudgeScore        = $null
            HumanReviewRequired = $true
            Failure             = $_.Exception.Message
        })

        Write-Log "[$index/$ScenarioCount] Could not parse validation output for $scenarioId. Recorded and continuing." "WARN"
        continue
    }

    # AI Judge
    $judgeScore = $null
    $humanReviewRequired = $null

    if (-not $SkipJudge) {
        $judgeLog = Join-Path $OutputDirectory "$scenarioId-judge.log"

        $judgeCommand = Invoke-Python `
            -Arguments @(
                "-m", "evaluation.cli",
                "judge-result",
                "--result-id", [string]$latest.result_id
            ) `
            -LogFile $judgeLog `
            -AllowFailure

        if ($judgeCommand.ExitCode -ne 0) {
            Write-Log "[$index/$ScenarioCount] AI Judge failed for $scenarioId. Deterministic result will still be saved. See $judgeLog" "WARN"
            $humanReviewRequired = $true
        }
        else {
            try {
                $judge = ConvertFrom-CommandJson `
                    -Text $judgeCommand.Output `
                    -Context "AI Judge for $scenarioId"

                if ($null -ne $judge.primary) {
                    $judgeScore = $judge.primary.weighted_score
                }

                if ($null -ne $judge.human_review) {
                    $humanReviewRequired = $judge.human_review.required
                }
            }
            catch {
                Write-Log "[$index/$ScenarioCount] Could not parse AI Judge output for $scenarioId. Deterministic result will still be saved." "WARN"
                $humanReviewRequired = $true
            }
        }
    }

    $progressRow = [PSCustomObject]@{
        Domain              = $domain
        ScenarioId          = $scenarioId
        ResultId            = $latest.result_id
        RunId               = $validation.run_id
        InvestigationId     = $latest.investigation_id
        RowStatus           = $latest.row_status
        InvestigationStatus = $latest.investigation_status
        CanonicalEntity     = $validation.canonical_investigated_entity
        BenchmarkValidity   = $validation.benchmark_validity
        DeterministicScore  = $validation.final_score
        Classification      = $validation.classification
        AIJudgeScore        = $judgeScore
        HumanReviewRequired = $humanReviewRequired
        Failure             = $latest.failure
    }

    Save-ProgressRow -Row $progressRow

    Write-Log (
        "[$index/$ScenarioCount] Completed {0}: deterministic={1}, judge={2}, classification={3}" -f
        $scenarioId,
        $validation.final_score,
        $judgeScore,
        $validation.classification
    ) "PASS"

    if (
        $StopOnApplicationFailure -and
        $validation.classification -ne "pass"
    ) {
        throw "$scenarioId was a genuine application failure and StopOnApplicationFailure was enabled."
    }
}

# -------------------------------------------------------------------------
# 6. Generate final summary
# -------------------------------------------------------------------------
if (-not (Test-Path $ProgressCsv)) {
    throw "Progress CSV was not created; no completed benchmark results are available."
}

$summaryHelper = @'
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

csv_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
md_path = Path(sys.argv[3])
detail_path = Path(sys.argv[4])
expected_count = int(sys.argv[5]) if len(sys.argv) > 5 else 100
included_domains = sys.argv[6] if len(sys.argv) > 6 else "Banking, Orders, Shipping, Clinic"

attempt_rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))

latest = {}
attempt_counts = defaultdict(int)
for row in attempt_rows:
    attempt_counts[row["ScenarioId"]] += 1
    latest[row["ScenarioId"]] = row
rows = list(latest.values())

def number(value):
    try:
        return float(value)
    except Exception:
        return None

def is_true(value):
    return str(value).strip().lower() == "true"

by_domain = defaultdict(list)
for row in rows:
    by_domain[row["Domain"]].append(row)

summary = {
    # Compatibility: scenario_count continues to mean latest selected unique scenarios.
    "scenario_count": len(rows),
    "attempt_count": len(attempt_rows),
    "unique_scenario_count": len(rows),
    "invalid_attempt_count": sum(
        1 for row in attempt_rows
        if str(row.get("RowStatus", "")).lower() == "invalid_configuration"
    ),
    "rerun_attempt_count": len(attempt_rows) - len(rows),
    "valid_count": sum(
        1 for row in rows
        if str(row["BenchmarkValidity"]).lower() == "valid"
    ),
    "pass_count": sum(
        1 for row in rows
        if str(row["Classification"]).lower() == "pass"
    ),
    "skipped_count": sum(
        1 for row in rows
        if str(row["Classification"]).lower().startswith("skipped_")
    ),
    "invalid_configuration_count": sum(
        1 for row in rows
        if str(row.get("RowStatus", "")).lower() == "invalid_configuration"
    ),
    "human_review_count": sum(
        1 for row in rows
        if is_true(row["HumanReviewRequired"])
    ),
    "overall_average_deterministic": None,
    "overall_average_ai_judge": None,
    "domains": {},
}

deterministic = [
    number(row["DeterministicScore"])
    for row in rows
]
deterministic = [value for value in deterministic if value is not None]

judge = [
    number(row["AIJudgeScore"])
    for row in rows
]
judge = [value for value in judge if value is not None]

if deterministic:
    summary["overall_average_deterministic"] = (
        sum(deterministic) / len(deterministic)
    )

if judge:
    summary["overall_average_ai_judge"] = (
        sum(judge) / len(judge)
    )

for domain, domain_rows in sorted(by_domain.items()):
    domain_det = [
        number(row["DeterministicScore"])
        for row in domain_rows
    ]
    domain_det = [value for value in domain_det if value is not None]

    domain_judge = [
        number(row["AIJudgeScore"])
        for row in domain_rows
    ]
    domain_judge = [value for value in domain_judge if value is not None]

    summary["domains"][domain] = {
        "scenario_count": len(domain_rows),
        "pass_count": sum(
            1 for row in domain_rows
            if str(row["Classification"]).lower() == "pass"
        ),
        "average_deterministic": (
            sum(domain_det) / len(domain_det)
            if domain_det else None
        ),
        "average_ai_judge": (
            sum(domain_judge) / len(domain_judge)
            if domain_judge else None
        ),
        "human_review_count": sum(
            1 for row in domain_rows
            if is_true(row["HumanReviewRequired"])
        ),
    }

json_path.write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8"
)

details = []
for row in rows:
    details.append({
        "scenario_id": row.get("ScenarioId"),
        "domain": row.get("Domain"),
        "run_id": row.get("RunId"),
        "investigation_id": row.get("InvestigationId"),
        "row_status": row.get("RowStatus"),
        "investigation_status": row.get("InvestigationStatus"),
        "classification": row.get("Classification"),
        "validity": row.get("BenchmarkValidity"),
        "failure": row.get("Failure"),
        "ai_invoked": row.get("AIInvoked"),
        "ai_outcome": row.get("AIOutcome"),
        "ai_skip_reason": row.get("AISkipReason"),
        "ai_diagnostic_category": row.get("AIDiagnosticCategory"),
        "model": row.get("LLMModelName"),
        "prompt_version": row.get("PromptVersion"),
        "input_tokens": number(row.get("InputTokens")),
        "output_tokens": number(row.get("OutputTokens")),
        "timestamp": row.get("Timestamp"),
        "attempt_count": attempt_counts[row["ScenarioId"]],
        "is_latest_attempt": True,
    })
detail_path.write_text(json.dumps({
    "schema_version": 1,
    "description": "Latest selected result per scenario; benchmark-progress.csv is the append-only attempt ledger.",
    "aggregate_scoring_uses_latest_attempt": True,
    "results": details,
}, indent=2), encoding="utf-8")

lines = [
    f"# {expected_count}-Scenario Validation Benchmark Summary",
    "",
    f"- Included domains: {included_domains}",
    "",
    f"- Scenarios recorded: {summary['scenario_count']}/{expected_count}",
    f"- Attempts recorded: {summary['attempt_count']}",
    f"- Unique scenarios: {summary['unique_scenario_count']}",
    f"- Rerun attempts: {summary['rerun_attempt_count']}",
    f"- Valid results: {summary['valid_count']}",
    f"- Passing results: {summary['pass_count']}",
    f"- Skipped/error results: {summary['skipped_count']}",
    f"- Invalid configuration results: {summary['invalid_configuration_count']}",
    f"- Human review required: {summary['human_review_count']}",
    f"- Average deterministic score: {summary['overall_average_deterministic']}",
    f"- Average AI Judge score: {summary['overall_average_ai_judge']}",
    "",
    "| Domain | Scenarios | Passes | Avg deterministic | Avg AI Judge | Human review |",
    "|---|---:|---:|---:|---:|---:|",
]

for domain, value in summary["domains"].items():
    lines.append(
        f"| {domain} | "
        f"{value['scenario_count']} | "
        f"{value['pass_count']} | "
        f"{value['average_deterministic']} | "
        f"{value['average_ai_judge']} | "
        f"{value['human_review_count']} |"
    )

md_path.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)

print(json.dumps(summary, indent=2))
'@

$summaryLines = @(
    $summaryHelper |
    & $Python - $ProgressCsv $SummaryJson $SummaryMd $DetailJson $ScenarioCount ($IncludedDomains -join ', ')
)

if ($LASTEXITCODE -ne 0) {
    throw "Unable to generate benchmark summary."
}

$summaryText = (
    $summaryLines |
    ForEach-Object { [string]$_ }
) -join [Environment]::NewLine

Write-Host $summaryText
Set-Content `
    -Path (Join-Path $OutputDirectory "summary-console.log") `
    -Value $summaryText `
    -Encoding UTF8

Write-Log "Benchmark processing completed." "PASS"

Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  $ProgressCsv"
Write-Host "  $SummaryJson"
Write-Host "  $SummaryMd"
Write-Host "  $DetailJson"
Write-Host "  $MasterLog"

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
$Generator = Join-Path $ProjectRoot "evaluation\generate_combined_dashboard_v3.py"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

if (-not (Test-Path $Generator)) {
    throw "Dashboard generator not found: $Generator"
}

$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputPath))
New-Item -ItemType Directory -Path (Split-Path $OutputPath -Parent) -Force | Out-Null

$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $ProjectRoot

try {
    $Arguments = @(
        $Generator,
        "--output",
        $OutputPath
    )

    if ($IncludeInvalid) {
        $Arguments += "--include-invalid"
    }

    & $Python @Arguments

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

Write-Host ""
Write-Host "Combined dashboard created:" -ForegroundColor Green
Write-Host $OutputPath

if ($OpenReport) {
    Start-Process $OutputPath
}

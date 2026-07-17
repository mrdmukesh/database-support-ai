Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script:EnvFile = Join-Path $script:RepoRoot '.env.evaluation'
$script:Python = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'

function Import-EvaluationEnvironment {
    if (-not (Test-Path -LiteralPath $script:EnvFile)) {
        throw "Missing $script:EnvFile"
    }
    foreach ($raw in Get-Content -LiteralPath $script:EnvFile) {
        $line = $raw.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            [Environment]::SetEnvironmentVariable(
                $parts[0].Trim(),
                $parts[1].Trim().Trim('"').Trim("'"),
                'Process'
            )
        }
    }
}

function Wait-LocalApi {
    param([int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 3
            if ($response.StatusCode -eq 200) { return }
        } catch {}
        Start-Sleep -Seconds 2
    }
    throw 'Local evaluation API did not become healthy'
}

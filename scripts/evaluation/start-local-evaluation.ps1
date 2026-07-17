. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:RepoRoot
Import-EvaluationEnvironment

$runtime = Join-Path $script:RepoRoot '.tmp\local-evaluation'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

$api = Start-Process -FilePath $script:Python `
    -ArgumentList '-m','uvicorn','legacydb_copilot.main:app','--host','127.0.0.1','--port','8000' `
    -WorkingDirectory $script:RepoRoot `
    -RedirectStandardOutput (Join-Path $runtime 'api.out.log') `
    -RedirectStandardError (Join-Path $runtime 'api.err.log') `
    -WindowStyle Hidden -PassThru
$api.Id | Set-Content -LiteralPath (Join-Path $runtime 'api.pid')
Wait-LocalApi

$worker = Start-Process -FilePath $script:Python `
    -ArgumentList '-m','evaluation.worker','--poll-seconds','2' `
    -WorkingDirectory $script:RepoRoot `
    -RedirectStandardOutput (Join-Path $runtime 'worker.out.log') `
    -RedirectStandardError (Join-Path $runtime 'worker.err.log') `
    -WindowStyle Hidden -PassThru
$worker.Id | Set-Content -LiteralPath (Join-Path $runtime 'worker.pid')

Write-Host 'Local API: http://127.0.0.1:8000'
Write-Host 'Local UI:  http://127.0.0.1:8000/react'
Write-Host "API PID: $($api.Id); worker PID: $($worker.Id)"

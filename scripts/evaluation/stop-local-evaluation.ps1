. (Join-Path $PSScriptRoot 'common.ps1')
$runtime = Join-Path $script:RepoRoot '.tmp\local-evaluation'
foreach ($name in 'api','worker') {
    $pidFile = Join-Path $runtime "$name.pid"
    if (Test-Path -LiteralPath $pidFile) {
        $processId = [int](Get-Content -LiteralPath $pidFile)
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $pidFile -Force
        Write-Host "Stopped $name process $processId"
    }
}

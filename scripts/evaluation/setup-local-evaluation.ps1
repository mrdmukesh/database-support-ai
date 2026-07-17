. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:RepoRoot
Import-EvaluationEnvironment

Write-Host '[1/6] Creating isolated MySQL databases and users'
& $script:Python -m evaluation.local_environment provision
if ($LASTEXITCODE) { throw 'MySQL provisioning failed' }
Import-EvaluationEnvironment

Write-Host '[2/6] Migrating application metadata database'
$applicationUrl = $env:DATABASE_URL
$resultsUrl = $env:EVAL_RESULTS_DATABASE_URL
$env:DATABASE_URL = $applicationUrl
& $script:Python -m alembic upgrade 0001_initial_schema
if ($LASTEXITCODE) { throw 'Application migration failed' }
& $script:Python -m alembic stamp head
if ($LASTEXITCODE) { throw 'Application migration stamp failed' }

Write-Host '[3/6] Migrating evaluation-results database'
$env:DATABASE_URL = $resultsUrl
& $script:Python -m alembic upgrade 0001_initial_schema
if ($LASTEXITCODE) { throw 'Evaluation-results migration failed' }
& $script:Python -m alembic stamp head
if ($LASTEXITCODE) { throw 'Evaluation-results migration stamp failed' }
$env:DATABASE_URL = $applicationUrl

Write-Host '[4/6] Loading five translated benchmark baselines'
& $script:Python -m evaluation.local_environment load-domains
if ($LASTEXITCODE) { throw 'Benchmark baseline load failed' }

Write-Host '[5/6] Creating local tenant, service account, and connections'
& $script:Python -m evaluation.local_environment bootstrap-app
if ($LASTEXITCODE) { throw 'Application bootstrap failed' }

Write-Host '[6/6] Local evaluation setup complete'
Write-Host 'Run: .\scripts\evaluation\start-local-evaluation.ps1'

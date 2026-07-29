param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$ServerName,
    [string]$ServiceObjective = 'Basic',
    [string]$ReaderPrincipal = 'eval_demo_payroll_reader',
    [switch]$ConfirmIsolatedEvaluationTarget
)

$ErrorActionPreference = 'Stop'
$database = 'EvalDemoPayrollV2'
$sourceDatabase = 'DemoPayrollV2'
$sqlRoot = Join-Path $PSScriptRoot 'demo_payroll/sql'

if (-not $ConfirmIsolatedEvaluationTarget) {
    throw 'Specify -ConfirmIsolatedEvaluationTarget to provision the disposable EvalDemoPayrollV2 database.'
}
if ($database -eq $sourceDatabase -or -not $database.StartsWith('Eval')) {
    throw 'Evaluation database identity guard failed.'
}

az sql db create `
    --resource-group $ResourceGroup `
    --server $ServerName `
    --name $database `
    --service-objective $ServiceObjective `
    --backup-storage-redundancy Local
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create $database."
}

$authArgs = if ($env:EVAL_SQL_ADMIN -and $env:EVAL_SQL_PASSWORD) {
    @('-U', $env:EVAL_SQL_ADMIN, '-P', $env:EVAL_SQL_PASSWORD)
} else {
    @('-G')
}
$server = "tcp:$ServerName.database.windows.net,1433"
foreach ($script in '01_create.sql', '02_seed.sql', '03_validate.sql') {
    & sqlcmd -S $server @authArgs -N -b -d $database -i (Join-Path $sqlRoot $script)
    if ($LASTEXITCODE -ne 0) {
        throw "EvalDemoPayrollV2 deployment failed: $script"
    }
}
& sqlcmd -S $server @authArgs -N -b -d $database `
    -v "ReaderPrincipal=$ReaderPrincipal" `
    -i (Join-Path $sqlRoot '06_configure_reader.sql')
if ($LASTEXITCODE -ne 0) {
    throw 'EvalDemoPayrollV2 reader-role configuration failed.'
}

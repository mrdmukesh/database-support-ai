param(
    [string]$ResourceGroup = $env:EVAL_DEMO_PAYROLL_RESOURCE_GROUP,
    [Parameter(Mandatory = $true)][string]$ServerName,
    [string]$ServiceObjective = 'Basic',
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
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    throw 'EVAL_DEMO_PAYROLL_RESOURCE_GROUP or -ResourceGroup is required.'
}
if (
    [string]::IsNullOrWhiteSpace($env:EVAL_DEMO_PAYROLL_READER) -or
    [string]::IsNullOrWhiteSpace($env:EVAL_DEMO_PAYROLL_READER_PASSWORD)
) {
    throw 'Dedicated EvalDemoPayrollV2 reader settings are required.'
}
if (
    [string]::IsNullOrWhiteSpace($env:EVAL_SQL_ADMIN) -or
    [string]::IsNullOrWhiteSpace($env:EVAL_SQL_PASSWORD)
) {
    throw 'Evaluation administrator settings are required.'
}

$ReaderPrincipal = $env:EVAL_DEMO_PAYROLL_READER
if (
    $ReaderPrincipal.Equals($env:EVAL_SQL_ADMIN, [StringComparison]::OrdinalIgnoreCase) -or
    $env:EVAL_DEMO_PAYROLL_READER_PASSWORD -ceq $env:EVAL_SQL_PASSWORD
) {
    throw 'EvalDemoPayrollV2 reader credentials must differ from administrator credentials.'
}

$allowedHostsValue = if ($env:EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS) {
    $env:EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS
} else {
    $env:EVAL_ALLOWED_SQL_HOSTS
}
$allowedHosts = @(
    $allowedHostsValue.Split(',') |
        ForEach-Object { $_.Trim().ToLowerInvariant() } |
        Where-Object { $_ }
)
$sqlHost = "$ServerName.database.windows.net".ToLowerInvariant()
if ($sqlHost -notin $allowedHosts) {
    throw 'EvalDemoPayrollV2 SQL host is not explicitly allowlisted.'
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

$authArgs = @('-U', $env:EVAL_SQL_ADMIN)
$previousSqlCmdPassword = $env:SQLCMDPASSWORD
$env:SQLCMDPASSWORD = $env:EVAL_SQL_PASSWORD
$server = "tcp:$ServerName.database.windows.net,1433"
try {
    foreach ($script in '01_create.sql', '02_seed.sql', '03_validate.sql') {
        & sqlcmd -S $server @authArgs -N -b -d $database -i (Join-Path $sqlRoot $script)
        if ($LASTEXITCODE -ne 0) {
            throw "EvalDemoPayrollV2 deployment failed: $script"
        }
    }
} finally {
    $env:SQLCMDPASSWORD = $previousSqlCmdPassword
}

$adminConnectionString = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
$adminConnectionString['Data Source'] = $server
$adminConnectionString['Initial Catalog'] = $database
$adminConnectionString['User ID'] = $env:EVAL_SQL_ADMIN
$adminConnectionString['Password'] = $env:EVAL_SQL_PASSWORD
$adminConnectionString['Encrypt'] = $true
$adminConnectionString['TrustServerCertificate'] = $false

$connection = New-Object System.Data.SqlClient.SqlConnection(
    $adminConnectionString.ConnectionString
)
try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = @'
IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51140, 'Reader creation refused: unexpected database identity', 1;

DECLARE @type CHAR(1);
DECLARE @authentication NVARCHAR(60);
SELECT @type = [type], @authentication = authentication_type_desc
FROM sys.database_principals
WHERE [name] = @reader;

IF @type IS NULL
BEGIN
    DECLARE @create NVARCHAR(MAX) =
        N'CREATE USER ' + QUOTENAME(@reader)
        + N' WITH PASSWORD = ' + QUOTENAME(@password, N'''');
    EXEC sys.sp_executesql @create;
END
ELSE IF @type <> 'S' OR @authentication <> N'DATABASE'
    THROW 51111, 'Existing reader principal is not a contained SQL user', 1;
'@
    [void]$command.Parameters.Add('@reader', [System.Data.SqlDbType]::NVarChar, 128)
    [void]$command.Parameters.Add('@password', [System.Data.SqlDbType]::NVarChar, 128)
    $command.Parameters['@reader'].Value = $ReaderPrincipal
    $command.Parameters['@password'].Value = $env:EVAL_DEMO_PAYROLL_READER_PASSWORD
    [void]$command.ExecuteNonQuery()
} finally {
    $connection.Dispose()
}

$readerConnectionString = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
$readerConnectionString['Data Source'] = $server
$readerConnectionString['Initial Catalog'] = $database
$readerConnectionString['User ID'] = $ReaderPrincipal
$readerConnectionString['Password'] = $env:EVAL_DEMO_PAYROLL_READER_PASSWORD
$readerConnectionString['Encrypt'] = $true
$readerConnectionString['TrustServerCertificate'] = $false
$readerConnection = New-Object System.Data.SqlClient.SqlConnection(
    $readerConnectionString.ConnectionString
)
try {
    $readerConnection.Open()
} catch {
    throw 'Existing EvalDemoPayrollV2 reader could not be validated with the approved credential.'
} finally {
    $readerConnection.Dispose()
}

$previousSqlCmdPassword = $env:SQLCMDPASSWORD
$env:SQLCMDPASSWORD = $env:EVAL_SQL_PASSWORD
try {
    & sqlcmd -S $server @authArgs -N -b -d $database `
    -v "ReaderPrincipal=$ReaderPrincipal" `
    -i (Join-Path $sqlRoot '06_configure_reader.sql')
    if ($LASTEXITCODE -ne 0) {
        throw 'EvalDemoPayrollV2 reader-role configuration failed.'
    }
} finally {
    $env:SQLCMDPASSWORD = $previousSqlCmdPassword
}

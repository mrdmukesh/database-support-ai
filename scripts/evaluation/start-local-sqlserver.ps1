. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:RepoRoot
Import-EvaluationEnvironment

$ErrorActionPreference = 'Stop'
$container = 'legacydb-evaluation-sqlserver'
$image = if ($env:LOCAL_SQLSERVER_IMAGE) { $env:LOCAL_SQLSERVER_IMAGE } else { 'mcr.microsoft.com/mssql/server:2022-latest' }
$port = if ($env:LOCAL_SQLSERVER_PORT) { $env:LOCAL_SQLSERVER_PORT } else { '14333' }
$password = $env:EVAL_SQL_PASSWORD
if (-not $password) { throw 'EVAL_SQL_PASSWORD is required' }

docker version | Out-Null
$runtime = Join-Path $script:RepoRoot '.tmp\local-sqlserver'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$envFile = Join-Path $runtime 'container.env'
[System.IO.File]::WriteAllText(
    $envFile,
    "ACCEPT_EULA=Y`nMSSQL_PID=Developer`nMSSQL_SA_PASSWORD=$password`n",
    (New-Object System.Text.UTF8Encoding($false))
)

$exists = docker ps -a --filter "name=^/$container$" --format '{{.Names}}'
if (-not $exists) {
    $dockerArgs = @(
        'run','-d','--name',$container,'--hostname','legacydb-eval-sql',
        '--env-file',$envFile,
        '-p',"127.0.0.1:${port}:1433",
        '-v','legacydb-evaluation-sqlserver-data:/var/opt/mssql',
        $image
    )
    & docker @dockerArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create local SQL Server container' }
} else {
    docker start $container | Out-Null
}

$deadline = (Get-Date).AddMinutes(4)
do {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $ready = docker exec $container bash -lc 'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -Q "SELECT 1" -b' 2>$null
    $ErrorActionPreference = $previousPreference
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 4
} while ((Get-Date) -lt $deadline)
if ($LASTEXITCODE -ne 0) { throw 'Local SQL Server did not become ready' }

docker cp (Join-Path $script:RepoRoot 'evaluation_databases') "${container}:/tmp/evaluation_databases" | Out-Null
$databases = [ordered]@{ payroll='EvalPayroll'; clinic='EvalClinic'; orders='EvalOrders'; banking='EvalBanking'; shipping='EvalShipping' }
$escapedPassword = $password.Replace("'", "''")
$setupSql = Join-Path $runtime 'setup-logins-and-databases.sql'
$createDatabases = ($databases.Values | ForEach-Object { "IF DB_ID(N'$_') IS NULL CREATE DATABASE [$_];" }) -join [Environment]::NewLine
[System.IO.File]::WriteAllText(
    $setupSql,
    "$createDatabases`nIF SUSER_ID(N'evaladmin') IS NULL CREATE LOGIN [evaladmin] WITH PASSWORD=N'$escapedPassword', CHECK_POLICY=OFF;`nIF SUSER_ID(N'evalreader') IS NULL CREATE LOGIN [evalreader] WITH PASSWORD=N'$escapedPassword', CHECK_POLICY=OFF;`n",
    (New-Object System.Text.UTF8Encoding($false))
)
docker cp $setupSql "${container}:/tmp/setup-logins-and-databases.sql" | Out-Null
docker exec $container bash -lc 'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -i /tmp/setup-logins-and-databases.sql' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Database/login setup failed' }

foreach ($entry in $databases.GetEnumerator()) {
    $domain = $entry.Key; $database = $entry.Value
    docker exec -w "/tmp/evaluation_databases/$domain/sql" $container bash -lc "export SQLCMDPASSWORD=`"`$MSSQL_SA_PASSWORD`"; set -e; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -d '$database' -i 05_destroy.sql; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -d '$database' -i 01_create.sql; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -d '$database' -i 02_seed.sql; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -d '$database' -i 03_validate.sql" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Deployment failed for $database" }
}

$permissionsSql = Join-Path $runtime 'database-permissions.sql'
$permissionBatches = ($databases.Values | ForEach-Object {
    "USE [$_];`nGO`nIF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];`nGO`nALTER ROLE db_owner ADD MEMBER [evaladmin];`nGO`nIF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];`nGO`nALTER ROLE db_datareader ADD MEMBER [evalreader];`nGO"
}) -join "`n"
[System.IO.File]::WriteAllText($permissionsSql, $permissionBatches, (New-Object System.Text.UTF8Encoding($false)))
docker cp $permissionsSql "${container}:/tmp/database-permissions.sql" | Out-Null
docker exec $container bash -lc 'export SQLCMDPASSWORD="$MSSQL_SA_PASSWORD"; /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -i /tmp/database-permissions.sql' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Database permissions setup failed' }

$summary = [ordered]@{
    container = $container; image = $image; host = '127.0.0.1'; port = [int]$port
    persistent_volume = 'legacydb-evaluation-sqlserver-data'; databases = @($databases.Values)
    admin_login = 'evaladmin'; reader_login = 'evalreader'; password_present = $true
    deployed_at = (Get-Date).ToUniversalTime().ToString('o')
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtime 'deployment-summary.json') -Encoding utf8
Write-Host "Local SQL Server ready on 127.0.0.1:$port with five native evaluation databases."

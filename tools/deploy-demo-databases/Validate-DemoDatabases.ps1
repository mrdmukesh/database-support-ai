[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ServerFqdn,
    [ValidateSet('Entra','Sql')][string]$AuthenticationMode = 'Entra',
    [string]$SqlAdminUser,
    [string]$OutputDirectory = ''
)
$ErrorActionPreference='Stop'
$databases=@('DemoBankingV2','DemoPayrollV2','DemoOrdersV2','DemoShippingV2','DemoClinicV2')
$query=@'
SET NOCOUNT ON;
SELECT DB_NAME() database_name,
(SELECT COUNT(*) FROM sys.tables) table_count,
(SELECT COUNT(*) FROM sys.key_constraints WHERE type='PK') primary_key_count,
(SELECT COUNT(*) FROM sys.foreign_keys) foreign_key_count,
(SELECT COUNT(*) FROM sys.indexes WHERE index_id > 0) index_count,
(SELECT COUNT(*) FROM sys.views) view_count,
(SELECT COUNT(*) FROM sys.procedures) procedure_count,
(SELECT COUNT(*) FROM sys.objects WHERE type IN ('FN','IF','TF','FS','FT')) function_count,
(SELECT COUNT(*) FROM sys.triggers WHERE parent_class=1) trigger_count;
SELECT SUM(row_count) seed_row_count FROM sys.dm_db_partition_stats WHERE index_id IN (0,1);
'@
if(-not $OutputDirectory){$OutputDirectory=Join-Path $PSScriptRoot 'output'}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$results=@()
foreach($database in $databases){
    $args=@('-S',$ServerFqdn,'-d',$database,'-N','-b','-W','-s',',','-Q',$query)
    if($AuthenticationMode -eq 'Entra'){$args+='-G'}else{
        if(-not $SqlAdminUser -or -not $env:DEMO_SQL_PASSWORD){throw 'Sql authentication requires -SqlAdminUser and DEMO_SQL_PASSWORD.'}
        $env:SQLCMDPASSWORD=$env:DEMO_SQL_PASSWORD;$args+=@('-U',$SqlAdminUser)
    }
    try{$output=& sqlcmd @args;if($LASTEXITCODE -ne 0){throw "Validation failed for $database"};$results+=[pscustomobject]@{database=$database;status='PASS';output=@($output)}}
    catch{$results+=[pscustomobject]@{database=$database;status='FAIL';error='[REDACTED_ERROR]'};throw}
    finally{Remove-Item Env:\SQLCMDPASSWORD -ErrorAction SilentlyContinue}
}
$results|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $OutputDirectory 'database-validation.json') -Encoding utf8
$results

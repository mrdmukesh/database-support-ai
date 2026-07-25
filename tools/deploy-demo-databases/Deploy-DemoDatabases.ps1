[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)][string]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$ServerName,
    [Parameter(Mandatory)][string]$PackagePath,
    [ValidateSet('Demo','Test','Development','Production')][string]$Environment = 'Demo',
    [switch]$AllowProduction,
    [ValidateSet('Entra','Sql')][string]$AuthenticationMode = 'Entra',
    [string]$SqlAdminUser,
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$approved = [ordered]@{
    Banking='DemoBankingV2'; Payroll='DemoPayrollV2'; Orders='DemoOrdersV2'
    Shipping='DemoShippingV2'; Clinic='DemoClinicV2'
}
$order = @('Tables.sql','ForeignKeys.sql','SeedData.sql','Views.sql','StoredProcedures.sql','Functions.sql','Triggers.sql')
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-AzJson([string[]]$Arguments) {
    $raw = & az @Arguments --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI command failed: az $($Arguments[0..1] -join ' ')" }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw | ConvertFrom-Json
}
function Assert-SafeSql([string]$Path, [string]$Database) {
    $sql = Get-Content -Raw -LiteralPath $Path
    if ($sql -match '(?is)\bDROP\s+DATABASE\b|\bSINGLE_USER\b|\bROLLBACK\s+IMMEDIATE\b|\bCREATE\s+DATABASE\b') {
        throw "Unsafe SQL rejected: $Path"
    }
    $uses = @([regex]::Matches($sql, '(?im)^\s*USE\s+\[([^\]]+)\]') | ForEach-Object { $_.Groups[1].Value })
    if (@($uses).Count -ne 1 -or $uses[0] -ne $Database) { throw "Database routing mismatch: $Path" }
}
function Invoke-SqlFile([string]$Fqdn, [string]$Database, [string]$Path) {
    $args = @('-S', $Fqdn, '-d', $Database, '-N', '-b', '-r', '1', '-i', $Path)
    if ($AuthenticationMode -eq 'Entra') { $args += '-G' }
    else {
        if (-not $SqlAdminUser -or -not $env:DEMO_SQL_PASSWORD) {
            throw 'Sql authentication requires -SqlAdminUser and DEMO_SQL_PASSWORD.'
        }
        $env:SQLCMDPASSWORD = $env:DEMO_SQL_PASSWORD
        $args += @('-U', $SqlAdminUser)
    }
    try { & sqlcmd @args; if ($LASTEXITCODE -ne 0) { throw "SQL batch failed: $(Split-Path $Path -Leaf)" } }
    finally { Remove-Item Env:\SQLCMDPASSWORD -ErrorAction SilentlyContinue }
}

if ($Environment -eq 'Production' -and -not $AllowProduction) { throw 'Production deployment requires -AllowProduction.' }
if (-not (Test-Path -LiteralPath $PackagePath -PathType Container)) { throw "Package path not found: $PackagePath" }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot 'output' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$account = Invoke-AzJson @('account','show')
if ($account.id -ne $SubscriptionId) { Invoke-AzJson @('account','set','--subscription',$SubscriptionId) | Out-Null; $account=Invoke-AzJson @('account','show') }
$group = Invoke-AzJson @('group','show','--name',$ResourceGroup,'--subscription',$SubscriptionId)
$server = Invoke-AzJson @('sql','server','show','--name',$ServerName,'--resource-group',$ResourceGroup,'--subscription',$SubscriptionId)
$fqdn = $server.fullyQualifiedDomainName
if (-not $fqdn) { throw 'Azure SQL logical server has no FQDN.' }
if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) { throw 'sqlcmd is required.' }
$existingDatabases = @(Invoke-AzJson @('sql','db','list','--server',$ServerName,'--resource-group',$ResourceGroup,'--subscription',$SubscriptionId))

foreach ($entry in $approved.GetEnumerator()) {
    $database = $entry.Value
    foreach ($script in $order) {
        Assert-SafeSql (Join-Path (Join-Path $PackagePath $entry.Key) $script) $database
    }
    $existing = $existingDatabases | Where-Object { $_.name -eq $database }
    if ($existing) { $results.Add([pscustomobject]@{database=$database;status='SKIPPED_ALREADY_EXISTS'}); continue }
    if (-not $PSCmdlet.ShouldProcess("$ServerName/$database", 'Create and install Azure SQL demo database')) {
        $results.Add([pscustomobject]@{database=$database;status='WOULD_CREATE'}); continue
    }
    try {
        Invoke-AzJson @('sql','db','create','--name',$database,'--server',$ServerName,'--resource-group',$ResourceGroup,'--subscription',$SubscriptionId,'--service-objective','Basic') | Out-Null
        foreach ($script in $order) {
            $path = Join-Path (Join-Path $PackagePath $entry.Key) $script
            Invoke-SqlFile $fqdn $database $path
        }
        $results.Add([pscustomobject]@{database=$database;status='CREATED_AND_INSTALLED'})
    } catch {
        $results.Add([pscustomobject]@{database=$database;status='FAILED';error='[REDACTED_ERROR]'})
        [ordered]@{
            timestamp=(Get-Date).ToUniversalTime().ToString('o')
            subscription_id=$account.id
            subscription_name=$account.name
            resource_group=$group.name
            server=$ServerName
            environment=$Environment
            results=$results
        } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'deployment-summary.json') -Encoding utf8
        throw
    }
}
$summary = [ordered]@{timestamp=(Get-Date).ToUniversalTime().ToString('o');subscription_id=$account.id;subscription_name=$account.name;resource_group=$group.name;server=$ServerName;environment=$Environment;results=$results}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'deployment-summary.json') -Encoding utf8
$summary

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ApiBaseUrl,
    [Parameter(Mandatory)][string]$OrganizationId,
    [Parameter(Mandatory)][string]$BearerToken,
    [Parameter(Mandatory)][string]$ServerFqdn,
    [Parameter(Mandatory)][string]$SecretRef
)
$ErrorActionPreference='Stop'
$headers=@{Authorization="Bearer $BearerToken"}
$name='Demo Evaluation Databases V2';$slug='demo-evaluation-databases-v2'
$existing=Invoke-RestMethod -Headers $headers -Uri "$ApiBaseUrl/workspaces?organization_id=$OrganizationId"
if($existing|Where-Object{$_.name -eq $name -or $_.slug -eq $slug}){throw 'A matching workspace already exists; refusing to modify it.'}
if(-not $PSCmdlet.ShouldProcess($name,'Create workspace and five demo connections')){return}
$workspace=Invoke-RestMethod -Method Post -Headers $headers -ContentType 'application/json' -Uri "$ApiBaseUrl/workspaces" -Body (@{organization_id=$OrganizationId;name=$name;slug=$slug}|ConvertTo-Json)
$connections=[ordered]@{'Demo Banking V2'='DemoBankingV2';'Demo Payroll V2'='DemoPayrollV2';'Demo Orders V2'='DemoOrdersV2';'Demo Shipping V2'='DemoShippingV2';'Demo Clinic V2'='DemoClinicV2'}
$result=@()
foreach($item in $connections.GetEnumerator()){
    $payload=@{organization_id=$OrganizationId;workspace_id=$workspace.id;engine='sql_server';name=$item.Key;host=$ServerFqdn;port=1433;database_name=$item.Value;secret_ref=$SecretRef}|ConvertTo-Json
    $connection=Invoke-RestMethod -Method Post -Headers $headers -ContentType 'application/json' -Uri "$ApiBaseUrl/databases/connections" -Body $payload
    $test=Invoke-RestMethod -Method Post -Headers $headers -Uri "$ApiBaseUrl/databases/connections/$($connection.id)/test"
    $result+=[pscustomobject]@{name=$item.Key;database=$item.Value;connection_id=$connection.id;test=$test}
}
[pscustomobject]@{workspace_id=$workspace.id;workspace_name=$workspace.name;connections=$result}


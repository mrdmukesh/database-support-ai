param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$ServerName,
    [Parameter(Mandatory = $true)][string]$Location
)

$databases = [ordered]@{
    payroll = 'EvalPayroll'
    clinic = 'EvalClinic'
    orders = 'EvalOrders'
    banking = 'EvalBanking'
    shipping = 'EvalShipping'
}

az group create --name $ResourceGroup --location $Location
foreach ($entry in $databases.GetEnumerator()) {
    az sql db create --resource-group $ResourceGroup --server $ServerName --name $entry.Value --service-objective S0 --backup-storage-redundancy Local
    foreach ($script in '01_create.sql', '02_seed.sql', '03_validate.sql') {
        sqlcmd -S "tcp:$ServerName.database.windows.net,1433" -G -N -b -d $entry.Value -i "$PSScriptRoot/$($entry.Key)/sql/$script"
        if ($LASTEXITCODE -ne 0) { throw "Azure deployment failed: $($entry.Key)/$script" }
    }
}

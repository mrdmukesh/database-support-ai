param(
    [Parameter(Mandatory = $true)][string]$Server,
    [Parameter(Mandatory = $true)][string]$AdminUser,
    [Parameter(Mandatory = $true)][SecureString]$Password
)

$plainPassword = [System.Net.NetworkCredential]::new('', $Password).Password
$databases = [ordered]@{
    payroll = 'EvalPayroll'
    clinic = 'EvalClinic'
    orders = 'EvalOrders'
    banking = 'EvalBanking'
    shipping = 'EvalShipping'
}

foreach ($entry in $databases.GetEnumerator()) {
    sqlcmd -S $Server -U $AdminUser -P $plainPassword -C -b -Q "IF DB_ID('$($entry.Value)') IS NULL CREATE DATABASE [$($entry.Value)]"
    foreach ($script in '01_create.sql', '02_seed.sql', '03_validate.sql') {
        sqlcmd -S $Server -U $AdminUser -P $plainPassword -C -b -d $entry.Value -i "$PSScriptRoot/$($entry.Key)/sql/$script"
        if ($LASTEXITCODE -ne 0) { throw "Deployment failed: $($entry.Key)/$script" }
    }
}

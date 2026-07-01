param(
    [string]$ResourceGroup = "rg-database-support-ai-dev",
    [string]$ContainerAppName = "ca-database-support-ai-dev",
    [Parameter(Mandatory = $true)]
    [string]$PostgresServerName,
    [string]$DatabaseName = "database_support_ai",
    [string]$AdminUser = "appadmin"
)

$password = Read-Host "PostgreSQL admin password" -AsSecureString
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

$hostName = "$PostgresServerName.postgres.database.azure.com"
$databaseUrl = "postgresql+psycopg://$AdminUser`:$plainPassword@$hostName`:5432/$DatabaseName`?sslmode=require"

az containerapp secret set `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --secrets "database-url=$databaseUrl"

az containerapp update `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --set-env-vars "DATABASE_URL=secretref:database-url"

Write-Host "DATABASE_URL secret configured for $ContainerAppName"

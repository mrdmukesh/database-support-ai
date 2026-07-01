# Azure PostgreSQL Internal App Database

The Azure Container App can run with temporary SQLite for a smoke test, but real
testing needs a persistent internal application database.

This database stores app data only:

- users and login data
- organizations and workspaces
- saved database connections
- uploaded document metadata
- investigations, feedback, and approved knowledge
- generated report metadata

It is separate from the customer database that the support AI investigates.

## Lowest-Cost Test Shape

Use Azure Database for PostgreSQL Flexible Server with the smallest available
burstable configuration in the same region as the Container App.

Current Azure resources:

```text
Resource group: rg-database-support-ai-dev
Container App: ca-database-support-ai-dev
Region: centralindia
```

Suggested names:

```text
PostgreSQL server: pg-database-support-ai-dev
Database name: database_support_ai
Admin user: appadmin
```

## Create PostgreSQL

Run from PowerShell after choosing a strong password:

```powershell
$rg = "rg-database-support-ai-dev"
$location = "centralindia"
$server = "pg-database-support-ai-dev"
$db = "database_support_ai"
$admin = "appadmin"
$password = Read-Host "PostgreSQL admin password" -AsSecureString
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

az postgres flexible-server create `
  --resource-group $rg `
  --location $location `
  --name $server `
  --database-name $db `
  --admin-user $admin `
  --admin-password $plainPassword `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --public-access 0.0.0.0
```

For quick testing, public access is simplest. For production, restrict network
access and prefer private networking.

## Configure Container App

Store the connection string as an Azure Container App secret:

```powershell
$hostName = "$server.postgres.database.azure.com"
$databaseUrl = "postgresql+psycopg://$admin`:$plainPassword@$hostName`:5432/$db?sslmode=require"

az containerapp secret set `
  --name ca-database-support-ai-dev `
  --resource-group $rg `
  --secrets database-url="$databaseUrl"

az containerapp update `
  --name ca-database-support-ai-dev `
  --resource-group $rg `
  --set-env-vars DATABASE_URL=secretref:database-url
```

The FastAPI startup hook initializes the internal schema automatically.

## Verify

After deployment restarts, open:

```text
https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/health
```

Then use the app:

```text
https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/app.html
```

Create a new signup after switching from SQLite to PostgreSQL because the old
temporary SQLite data will not exist in the new database.

## Cost Control

- Keep Container App min replicas at `0`.
- Keep max replicas at `1` for testing.
- Stop or delete the PostgreSQL server when not needed for long periods.
- Do not enable OpenAI until you are ready to test LLM reasoning.

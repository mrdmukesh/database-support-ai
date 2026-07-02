# Azure Persistent Platform Layer

This project uses Azure Container Apps for the API/UI container and adds a
persistent app platform layer for production-like testing.

## Resources Created By CI/CD

The GitHub Actions workflow `.github/workflows/azure-container-app.yml` creates
or reuses these resources:

- Resource group: `rg-database-support-ai-dev`
- Container Apps environment: `cae-database-support-ai-dev`
- Container App: `ca-database-support-ai-dev`
- Azure PostgreSQL Flexible Server for internal app data
- Azure Storage Account with private Blob container for uploads and reports
- Azure Key Vault for app runtime secrets

Resource names that must be globally unique are derived from the Azure
subscription ID, so the workflow can recreate resources after the resource group
is deleted.

## Required GitHub Secrets

Configure these repository secrets:

- `AZURE_CREDENTIALS`: service principal JSON used by `azure/login`.
- `AZURE_POSTGRES_ADMIN_PASSWORD`: strong PostgreSQL admin password used when
  the PostgreSQL server must be created.

The service principal in `AZURE_CREDENTIALS` must have enough subscription-level
permission to create a resource group and resources inside it.

## Secret Flow

The workflow stores runtime values in Azure Key Vault:

- `database-url`
- `jwt-secret`
- `azure-storage-connection-string`

During deployment, the workflow reads those Key Vault secrets and sets Azure
Container App secrets:

- `DATABASE_URL=secretref:database-url`
- `JWT_SECRET=secretref:jwt-secret`
- `AZURE_STORAGE_CONNECTION_STRING=secretref:storage-connection-string`

The app receives:

```text
STORAGE_BACKEND=azure_blob
AZURE_STORAGE_CONTAINER=app-artifacts
DATABASE_URL=postgresql+psycopg://...
```

## What Is Stored Where

PostgreSQL stores internal application data:

- users and login records
- organizations and workspaces
- saved database connection metadata
- uploaded document metadata
- chat and investigation history
- feedback and knowledge article records

Blob Storage stores files:

- uploaded documents
- generated HTML reports
- generated PDF reports
- generated Word reports
- generated Excel reports

Key Vault stores secrets:

- app database connection string
- JWT signing secret
- Blob Storage connection string

## Cost Notes

The workflow uses low-cost development settings:

- Container App min replicas: `0`
- Container App max replicas: `1`
- PostgreSQL tier: `Burstable`
- PostgreSQL SKU: `Standard_B1ms`
- Storage: `Standard_LRS`
- Key Vault: `standard`

Delete the resource group to stop the environment. Running the workflow again
recreates the hosting and persistence layer.

## Current Security Tradeoff

For simple development deployment, PostgreSQL public access is opened broadly by
the workflow. Before production, replace this with private networking or a
restricted outbound IP strategy.

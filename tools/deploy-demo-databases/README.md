# Demo Evaluation Databases V2 deployment

This tooling provisions five allowlisted Azure SQL demo databases without calling the
package's destructive `CreateDatabase.sql` files. Existing databases are never modified
and are reported as `SKIPPED_ALREADY_EXISTS`.

## Installation order

The original package dependency order is preserved: `Tables.sql`,
`ForeignKeys.sql`, `SeedData.sql`, `Views.sql`, `StoredProcedures.sql`,
`Functions.sql`, and `Triggers.sql`. Triggers intentionally follow seed loading.

## Prerequisites

Install and authenticate Azure CLI and `sqlcmd`. Use Entra authentication where
possible. SQL authentication reads its password only from `DEMO_SQL_PASSWORD` and
temporarily supplies it through `SQLCMDPASSWORD`; logs never include it.

```powershell
az login
.\tools\deploy-demo-databases\Deploy-DemoDatabases.ps1 `
  -SubscriptionId <subscription-id> -ResourceGroup <resource-group> `
  -ServerName <logical-server> `
  -PackagePath 'C:\Users\Admin\Downloads\EvaluationDatabasePack_v2.0\EvaluationDatabasePack_v2.0' `
  -Environment Demo -WhatIf
```

Remove `-WhatIf` only after reviewing the dry run. Then validate with
`Validate-DemoDatabases.ps1`. Register the workspace through
`Register-DemoWorkspace.ps1`, passing a Key Vault or environment secret reference,
never a raw credential.


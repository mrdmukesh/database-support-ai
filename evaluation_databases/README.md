# Synthetic Azure SQL evaluation databases

This directory contains five disposable, synthetic Azure SQL Database / SQL Server 2022 packages.
No customer, confidential, or production-derived data is used. Each package is deployed into its
own database and uses an `eval` schema.

## Deployment order

For each domain, run `01_create.sql`, `02_seed.sql`, then `03_validate.sql`. Use `04_reset.sql`
between scenarios and `05_destroy.sql` to remove the schema. Scenario order is `precondition.sql`,
`inject.sql`, `verify.sql`, investigation execution, and `cleanup.sql`.

Database names are `EvalPayroll`, `EvalClinic`, `EvalOrders`, `EvalBanking`, and `EvalShipping`.
Shipping has 34 tables because the requested container operating model cannot be represented
faithfully within the otherwise applicable 12–20 table guideline.

## Local SQL Server commands

```powershell
$env:EVAL_SQL_SERVER = "localhost,1433"
$env:EVAL_SQL_ADMIN = "sa"
$env:EVAL_SQL_PASSWORD = "<local-secret>"
sqlcmd -S $env:EVAL_SQL_SERVER -U $env:EVAL_SQL_ADMIN -P $env:EVAL_SQL_PASSWORD -C -Q "CREATE DATABASE EvalPayroll"
sqlcmd -S $env:EVAL_SQL_SERVER -U $env:EVAL_SQL_ADMIN -P $env:EVAL_SQL_PASSWORD -C -d EvalPayroll -b -i evaluation_databases/payroll/sql/01_create.sql
sqlcmd -S $env:EVAL_SQL_SERVER -U $env:EVAL_SQL_ADMIN -P $env:EVAL_SQL_PASSWORD -C -d EvalPayroll -b -i evaluation_databases/payroll/sql/02_seed.sql
sqlcmd -S $env:EVAL_SQL_SERVER -U $env:EVAL_SQL_ADMIN -P $env:EVAL_SQL_PASSWORD -C -d EvalPayroll -b -i evaluation_databases/payroll/sql/03_validate.sql
```

Repeat with the domain/database pairs `clinic/EvalClinic`, `orders/EvalOrders`,
`banking/EvalBanking`, and `shipping/EvalShipping`.

Deploy all five with an interactively supplied local password:

```powershell
./evaluation_databases/deploy-local.ps1 -Server "localhost,1433" -AdminUser "sa" -Password (Read-Host -AsSecureString "SQL password")
```

Run all opt-in database validations locally:

```powershell
$env:EVALUATION_SQLSERVER_INTEGRATION = "1"
pytest --basetemp=.test-tmp/evaluation-sql tests/test_evaluation_databases.py
```

## Azure deployment commands

These commands contain placeholders only. Supply credentials through Azure CLI, managed identity,
or a secret store; never commit passwords.

```powershell
az group create --name "<resource-group>" --location "<location>"
az sql server create --resource-group "<resource-group>" --name "<globally-unique-server>" --location "<location>" --admin-user "<admin-user>" --admin-password "<secret-from-secure-store>"
az sql server firewall-rule create --resource-group "<resource-group>" --server "<globally-unique-server>" --name "AllowDeploymentAgent" --start-ip-address "<agent-public-ip>" --end-ip-address "<agent-public-ip>"
az sql db create --resource-group "<resource-group>" --server "<globally-unique-server>" --name EvalPayroll --service-objective S0 --backup-storage-redundancy Local
sqlcmd -S "tcp:<globally-unique-server>.database.windows.net,1433" -G -d EvalPayroll -N -b -i evaluation_databases/payroll/sql/01_create.sql
sqlcmd -S "tcp:<globally-unique-server>.database.windows.net,1433" -G -d EvalPayroll -N -b -i evaluation_databases/payroll/sql/02_seed.sql
sqlcmd -S "tcp:<globally-unique-server>.database.windows.net,1433" -G -d EvalPayroll -N -b -i evaluation_databases/payroll/sql/03_validate.sql
```

Create and deploy the remaining four database names with the corresponding domain paths.

After the Azure SQL logical server and Microsoft Entra administrator exist, deploy all five using
the caller's Entra token (no SQL password):

```powershell
az login
./evaluation_databases/deploy-azure.ps1 -ResourceGroup "<resource-group>" -ServerName "<globally-unique-server>" -Location "<location>"
```

## Azure SQL limitations

- SQL Agent jobs are not created because Azure SQL Database does not provide SQL Server Agent;
  `batch_runs` models job execution and Azure Elastic Jobs or Automation can invoke procedures.
- Cross-database queries, CLR, filesystem access, linked servers, and server-level objects are not used.
- Destruction removes evaluation schema objects, not the Azure database or server.
- Microsoft Entra authentication requires tenant-side administrator configuration before `sqlcmd -G`.

# Local SQL Server Environment

- Status: READY
- Image: `mcr.microsoft.com/mssql/server:2022-latest`
- Container: `legacydb-evaluation-sqlserver`
- Binding: `127.0.0.1:14333` (localhost only)
- Persistent volume: `legacydb-evaluation-sqlserver-data`
- Databases: EvalPayroll, EvalClinic, EvalOrders, EvalBanking, EvalShipping
- Dedicated admin login: `evaladmin`
- Dedicated reader login: `evalreader`
- Password present: yes (not displayed)
- EvalShipping schema validation: PASS
- Native objects: 50
- Declared foreign keys: 26

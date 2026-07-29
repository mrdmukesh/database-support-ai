SET XACT_ABORT ON;

IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51130, 'Destroy refused: unexpected database identity', 1;
IF NOT EXISTS (
    SELECT 1
    FROM eval.evaluation_marker
    WHERE MarkerId = 1
      AND DomainName = N'demo_payroll'
      AND DatabaseName = DB_NAME()
      AND IsSynthetic = 1
)
    THROW 51131, 'Destroy refused: evaluation marker missing', 1;

BEGIN TRANSACTION;

DROP VIEW IF EXISTS dbo.vw_ActiveEmployee;
DROP PROCEDURE IF EXISTS dbo.usp_GetEmployeeAge;
DROP TABLE IF EXISTS fault.DeniedEvidence;
DROP TABLE IF EXISTS dbo.PayrollException;
DROP TABLE IF EXISTS dbo.PayrollItem;
DROP TABLE IF EXISTS dbo.PayrollRun;
DROP TABLE IF EXISTS dbo.Employee;
DROP TABLE IF EXISTS dbo.Department;
DROP TABLE IF EXISTS eval.evaluation_marker;

COMMIT;
GO

IF SCHEMA_ID(N'fault') IS NOT NULL EXEC(N'DROP SCHEMA fault');
IF SCHEMA_ID(N'eval') IS NOT NULL EXEC(N'DROP SCHEMA eval');
GO

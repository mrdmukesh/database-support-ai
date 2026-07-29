SET XACT_ABORT ON;

IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51120, 'Reset refused: unexpected database identity', 1;
IF NOT EXISTS (
    SELECT 1
    FROM eval.evaluation_marker
    WHERE MarkerId = 1
      AND DomainName = N'demo_payroll'
      AND DatabaseName = DB_NAME()
      AND IsSynthetic = 1
)
    THROW 51121, 'Reset refused: evaluation marker missing', 1;

BEGIN TRANSACTION;

DELETE FROM fault.DeniedEvidence;
DELETE FROM dbo.PayrollException;
DELETE FROM dbo.PayrollItem;
DELETE FROM dbo.PayrollRun;
DELETE FROM dbo.Employee;
DELETE FROM dbo.Department;
DELETE FROM eval.evaluation_marker;

DBCC CHECKIDENT ('fault.DeniedEvidence', RESEED, 0);
DBCC CHECKIDENT ('dbo.PayrollException', RESEED, 0);
DBCC CHECKIDENT ('dbo.PayrollItem', RESEED, 0);
DBCC CHECKIDENT ('dbo.PayrollRun', RESEED, 0);
DBCC CHECKIDENT ('dbo.Employee', RESEED, 0);
DBCC CHECKIDENT ('dbo.Department', RESEED, 0);

COMMIT;
GO
:r 02_seed.sql

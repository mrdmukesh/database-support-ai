:setvar ReaderPrincipal "eval_demo_payroll_reader"

IF DATABASE_PRINCIPAL_ID(N'eval_demo_payroll_readers') IS NULL
    CREATE ROLE eval_demo_payroll_readers;
GO

GRANT SELECT ON SCHEMA::dbo TO eval_demo_payroll_readers;
GRANT EXECUTE ON OBJECT::dbo.usp_GetEmployeeAge TO eval_demo_payroll_readers;
DENY SELECT ON OBJECT::fault.DeniedEvidence TO eval_demo_payroll_readers;
GO

DECLARE @principal SYSNAME = N'$(ReaderPrincipal)';
IF DATABASE_PRINCIPAL_ID(@principal) IS NULL
    THROW 51110, 'Reader principal must already exist in EvalDemoPayrollV2', 1;

DECLARE @statement NVARCHAR(MAX) =
    N'ALTER ROLE eval_demo_payroll_readers ADD MEMBER '
    + QUOTENAME(@principal);
EXEC sys.sp_executesql @statement;
GO

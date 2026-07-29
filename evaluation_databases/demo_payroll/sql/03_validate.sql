SET NOCOUNT ON;

IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51100, 'Unexpected database identity', 1;
IF NOT EXISTS (
    SELECT 1
    FROM eval.evaluation_marker
    WHERE MarkerId = 1
      AND DomainName = N'demo_payroll'
      AND DatabaseName = DB_NAME()
      AND IsSynthetic = 1
)
    THROW 51101, 'Evaluation marker missing', 1;
IF (SELECT COUNT(*) FROM dbo.Employee) <> 4
    THROW 51102, 'Employee fixture count mismatch', 1;
IF (SELECT COUNT(*) FROM dbo.Employee WHERE DateOfBirth IS NULL) <> 1
    THROW 51103, 'NULL fixture mismatch', 1;
IF OBJECT_ID(N'dbo.usp_GetEmployeeAge', N'P') IS NULL
    THROW 51104, 'Procedure fixture missing', 1;

SELECT N'VALID' AS FixtureStatus, 1 AS FixtureVersion;
GO

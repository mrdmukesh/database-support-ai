SET XACT_ABORT ON;

IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51150, 'Seed refused: unexpected database identity', 1;

BEGIN TRANSACTION;

INSERT eval.evaluation_marker
    (MarkerId, DomainName, DatabaseName, IsSynthetic, FixtureVersion)
VALUES
    (1, N'demo_payroll', DB_NAME(), 1, 1);

INSERT dbo.Department (DepartmentCode, DepartmentName)
VALUES (N'ENG', N'Engineering'), (N'OPS', N'Operations');

INSERT dbo.Employee
    (EmployeeNumber, EmployeeName, DateOfBirth, DepartmentId,
     EmploymentStatus, BusinessKey, Status, CorrelationId)
VALUES
    (N'VAL-2001', N'Valid Date Record', '1990-05-06', 1,
     N'Active', N'VAL-2001', N'Active', N'CORR-VAL-2001'),
    (N'NUL-2002', N'Nullable Date Record', NULL, 1,
     N'Active', N'NUL-2002', N'Active', N'CORR-NUL-2002'),
    (N'AMB-3001-A', N'Ambiguous Record A', '1988-03-02', 2,
     N'Active', N'AMB-3001-A', N'Active', N'CORR-AMB-A'),
    (N'AMB-3001-B', N'Ambiguous Record B', '1987-04-03', 2,
     N'Active', N'AMB-3001-B', N'Active', N'CORR-AMB-B');

INSERT dbo.PayrollRun
    (PeriodStart, PeriodEnd, BusinessKey, Status, CorrelationId)
VALUES
    ('2026-07-01', '2026-07-31', N'RUN-VALID-01', N'Completed', N'CORR-RUN-01');

INSERT dbo.PayrollItem
    (PayrollRunId, EmployeeId, GrossPay, NetPay, ErrorCode,
     BusinessKey, Status, CorrelationId)
SELECT 1, EmployeeId, 5000.00, 4200.00, NULL,
       N'ITEM-VAL-2001', N'Completed', N'CORR-VAL-2001'
FROM dbo.Employee
WHERE BusinessKey = N'VAL-2001';

INSERT fault.DeniedEvidence (BusinessKey, DiagnosticValue)
VALUES (N'DEN-4001', N'Evaluation-only permission boundary');

COMMIT;
GO

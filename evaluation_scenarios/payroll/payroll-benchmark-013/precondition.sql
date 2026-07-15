SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[deductions] WHERE BusinessKey LIKE N'PAY-2026-0013%' OR CorrelationId=N'EVAL-PAYROLL-113') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO

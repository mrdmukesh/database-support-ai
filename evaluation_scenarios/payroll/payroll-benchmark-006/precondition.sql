SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[employees] WHERE BusinessKey LIKE N'PAY-2026-0006%' OR CorrelationId=N'EVAL-PAYROLL-106') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO

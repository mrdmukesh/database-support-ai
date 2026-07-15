SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM eval.[payments] WHERE BusinessKey LIKE N'PAY-2026-0003%' OR CorrelationId=N'EVAL-PAYROLL-103') THROW 51101, 'Benchmark scenario contaminated before injection', 1;
SELECT N'precondition_valid' AS validation_status;
GO

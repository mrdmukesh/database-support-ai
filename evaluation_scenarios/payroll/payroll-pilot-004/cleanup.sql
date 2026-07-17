SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-PAYROLL-004';
UPDATE eval.[payroll_runs] SET BusinessKey=N'PAYROLL-008',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-PAYROLL' WHERE BusinessKey=N'RUN-2026-07-A' AND CorrelationId=N'EVAL-PAYROLL-004';
COMMIT;
GO

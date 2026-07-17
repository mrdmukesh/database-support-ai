SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-PAYROLL-003';
UPDATE eval.[time_entries] SET BusinessKey=N'PAYROLL-006',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-PAYROLL' WHERE BusinessKey=N'TIME-8821' AND CorrelationId=N'EVAL-PAYROLL-003';
COMMIT;
GO

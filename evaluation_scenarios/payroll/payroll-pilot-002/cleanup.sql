SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-PAYROLL-002';
UPDATE eval.[payments] SET BusinessKey=N'PAYROLL-011',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-PAYROLL' WHERE BusinessKey=N'PAY-7003' AND CorrelationId=N'EVAL-PAYROLL-002';
COMMIT;
GO

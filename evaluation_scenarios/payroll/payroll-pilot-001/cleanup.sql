SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-PAYROLL-001';
UPDATE eval.[employees] SET BusinessKey=N'PAYROLL-002',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-PAYROLL' WHERE BusinessKey=N'EMP-1042' AND CorrelationId=N'EVAL-PAYROLL-001';
COMMIT;
GO

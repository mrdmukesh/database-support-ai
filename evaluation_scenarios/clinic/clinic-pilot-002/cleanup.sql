SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-CLINIC-002';
UPDATE eval.[claims] SET BusinessKey=N'CLINIC-012',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-CLINIC' WHERE BusinessKey=N'CLM-3302' AND CorrelationId=N'EVAL-CLINIC-002';
COMMIT;
GO

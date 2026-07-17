SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-CLINIC-001';
UPDATE eval.[appointments] SET BusinessKey=N'CLINIC-004',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-CLINIC' WHERE BusinessKey=N'APT-2101' AND CorrelationId=N'EVAL-CLINIC-001';
COMMIT;
GO

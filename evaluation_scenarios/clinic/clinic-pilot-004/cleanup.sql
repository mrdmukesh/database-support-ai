SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-CLINIC-004';
UPDATE eval.[encounters] SET BusinessKey=N'CLINIC-005',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-CLINIC' WHERE BusinessKey=N'ENC-5504' AND CorrelationId=N'EVAL-CLINIC-004';
COMMIT;
GO

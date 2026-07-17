SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-BANKING-001';
UPDATE eval.[transfers] SET BusinessKey=N'BANKING-005',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-BANKING' WHERE BusinessKey=N'TRF-3101' AND CorrelationId=N'EVAL-BANKING-001';
COMMIT;
GO

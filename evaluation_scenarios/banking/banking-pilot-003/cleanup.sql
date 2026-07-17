SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-BANKING-003';
UPDATE eval.[accounts] SET BusinessKey=N'BANKING-002',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-BANKING' WHERE BusinessKey=N'ACC-3103' AND CorrelationId=N'EVAL-BANKING-003';
COMMIT;
GO

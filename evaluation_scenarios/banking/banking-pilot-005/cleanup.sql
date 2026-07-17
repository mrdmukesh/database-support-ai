SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-BANKING-005';
UPDATE eval.[transactions] SET BusinessKey=N'BANKING-004',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-BANKING' WHERE BusinessKey=N'TXN-3105' AND CorrelationId=N'EVAL-BANKING-005';
COMMIT;
GO

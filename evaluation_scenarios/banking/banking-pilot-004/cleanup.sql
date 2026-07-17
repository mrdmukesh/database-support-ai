SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-BANKING-004';
UPDATE eval.[batch_runs] SET BusinessKey=N'BANKING-014',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-BANKING' WHERE BusinessKey=N'BAT-3104' AND CorrelationId=N'EVAL-BANKING-004';
COMMIT;
GO

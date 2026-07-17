SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-BANKING-002';
UPDATE eval.[payment_instructions] SET BusinessKey=N'BANKING-007',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-BANKING' WHERE BusinessKey=N'PMT-3102' AND CorrelationId=N'EVAL-BANKING-002';
COMMIT;
GO

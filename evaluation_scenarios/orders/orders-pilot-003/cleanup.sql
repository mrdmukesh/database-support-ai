SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-ORDERS-003';
UPDATE eval.[products] SET BusinessKey=N'ORDERS-002',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-ORDERS' WHERE BusinessKey=N'SKU-8103' AND CorrelationId=N'EVAL-ORDERS-003';
COMMIT;
GO

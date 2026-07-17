SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-ORDERS-002';
UPDATE eval.[sales_orders] SET BusinessKey=N'ORDERS-006',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-ORDERS' WHERE BusinessKey=N'ORD-7102' AND CorrelationId=N'EVAL-ORDERS-002';
COMMIT;
GO

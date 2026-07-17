SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-ORDERS-001';
UPDATE eval.[sales_orders] SET BusinessKey=N'ORDERS-006',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-ORDERS' WHERE BusinessKey=N'ORD-7101' AND CorrelationId=N'EVAL-ORDERS-001';
COMMIT;
GO

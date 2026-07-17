SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-ORDERS-005';
UPDATE eval.[purchase_orders] SET BusinessKey=N'ORDERS-011',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-ORDERS' WHERE BusinessKey=N'PO-1205' AND CorrelationId=N'EVAL-ORDERS-005';
COMMIT;
GO

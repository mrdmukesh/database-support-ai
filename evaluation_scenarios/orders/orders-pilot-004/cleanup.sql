SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-ORDERS-004';
UPDATE eval.[pick_tasks] SET BusinessKey=N'ORDERS-009',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-ORDERS' WHERE BusinessKey=N'PICK-9104' AND CorrelationId=N'EVAL-ORDERS-004';
COMMIT;
GO

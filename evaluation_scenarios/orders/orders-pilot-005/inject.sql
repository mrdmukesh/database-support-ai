SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[purchase_orders] SET BusinessKey=N'PO-1205',Status=N'Exception',Details=N'EVAL-ORDERS-005',CorrelationId=N'EVAL-ORDERS-005' WHERE BusinessKey=N'ORDERS-011';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-ORDERS-005',N'Open',N'Synthetic pilot defect for PO-1205',N'EVAL-ORDERS-005');
COMMIT;
GO

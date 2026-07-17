SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[sales_orders] SET BusinessKey=N'ORD-7101',Status=N'Exception',Details=N'EVAL-ORDERS-001',CorrelationId=N'EVAL-ORDERS-001' WHERE BusinessKey=N'ORDERS-006';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-ORDERS-001',N'Open',N'Synthetic pilot defect for ORD-7101',N'EVAL-ORDERS-001');
COMMIT;
GO

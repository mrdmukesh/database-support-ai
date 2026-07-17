SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[products] SET BusinessKey=N'SKU-8103',Status=N'Exception',Details=N'EVAL-ORDERS-003',CorrelationId=N'EVAL-ORDERS-003' WHERE BusinessKey=N'ORDERS-002';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-ORDERS-003',N'Open',N'Synthetic pilot defect for SKU-8103',N'EVAL-ORDERS-003');
COMMIT;
GO

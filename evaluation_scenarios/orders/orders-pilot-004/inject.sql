SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[pick_tasks] SET BusinessKey=N'PICK-9104',Status=N'Exception',Details=N'EVAL-ORDERS-004',CorrelationId=N'EVAL-ORDERS-004' WHERE BusinessKey=N'ORDERS-009';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-ORDERS-004',N'Open',N'Synthetic pilot defect for PICK-9104',N'EVAL-ORDERS-004');
COMMIT;
GO

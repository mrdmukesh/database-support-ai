SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[claims] SET BusinessKey=N'CLM-3302',Status=N'Exception',Details=N'EVAL-CLINIC-002',CorrelationId=N'EVAL-CLINIC-002' WHERE BusinessKey=N'CLINIC-012';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-CLINIC-002',N'Open',N'Synthetic pilot defect for CLM-3302',N'EVAL-CLINIC-002');
COMMIT;
GO

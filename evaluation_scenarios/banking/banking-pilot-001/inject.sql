SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[transfers] SET BusinessKey=N'TRF-3101',Status=N'Exception',Details=N'EVAL-BANKING-001',CorrelationId=N'EVAL-BANKING-001' WHERE BusinessKey=N'BANKING-005';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-BANKING-001',N'Open',N'Synthetic pilot defect for TRF-3101',N'EVAL-BANKING-001');
COMMIT;
GO

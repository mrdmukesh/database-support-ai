SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[payment_instructions] SET BusinessKey=N'PMT-3102',Status=N'Exception',Details=N'EVAL-BANKING-002',CorrelationId=N'EVAL-BANKING-002' WHERE BusinessKey=N'BANKING-007';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-BANKING-002',N'Open',N'Synthetic pilot defect for PMT-3102',N'EVAL-BANKING-002');
COMMIT;
GO

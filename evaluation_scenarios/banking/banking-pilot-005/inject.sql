SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[transactions] SET BusinessKey=N'TXN-3105',Status=N'Exception',Details=N'EVAL-BANKING-005',CorrelationId=N'EVAL-BANKING-005' WHERE BusinessKey=N'BANKING-004';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-BANKING-005',N'Open',N'Synthetic pilot defect for TXN-3105',N'EVAL-BANKING-005');
COMMIT;
GO

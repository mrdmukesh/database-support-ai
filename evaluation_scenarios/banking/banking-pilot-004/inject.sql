SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[batch_runs] SET BusinessKey=N'BAT-3104',Status=N'Exception',Details=N'EVAL-BANKING-004',CorrelationId=N'EVAL-BANKING-004' WHERE BusinessKey=N'BANKING-014';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-BANKING-004',N'Open',N'Synthetic pilot defect for BAT-3104',N'EVAL-BANKING-004');
COMMIT;
GO

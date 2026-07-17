SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[encounters] SET BusinessKey=N'ENC-5504',Status=N'Exception',Details=N'EVAL-CLINIC-004',CorrelationId=N'EVAL-CLINIC-004' WHERE BusinessKey=N'CLINIC-005';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-CLINIC-004',N'Open',N'Synthetic pilot defect for ENC-5504',N'EVAL-CLINIC-004');
COMMIT;
GO

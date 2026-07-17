SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[appointments] SET BusinessKey=N'APT-2101',Status=N'Exception',Details=N'EVAL-CLINIC-001',CorrelationId=N'EVAL-CLINIC-001' WHERE BusinessKey=N'CLINIC-004';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-CLINIC-001',N'Open',N'Synthetic pilot defect for APT-2101',N'EVAL-CLINIC-001');
COMMIT;
GO

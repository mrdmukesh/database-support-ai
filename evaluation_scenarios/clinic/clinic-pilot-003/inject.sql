SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[lab_results] SET BusinessKey=N'LAB-4403',Status=N'Exception',Details=N'EVAL-CLINIC-003',CorrelationId=N'EVAL-CLINIC-003' WHERE BusinessKey=N'CLINIC-010';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-CLINIC-003',N'Open',N'Synthetic pilot defect for LAB-4403',N'EVAL-CLINIC-003');
COMMIT;
GO

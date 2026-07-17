SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[patients] SET BusinessKey=N'PAT-6605',Status=N'Exception',Details=N'EVAL-CLINIC-005',CorrelationId=N'EVAL-CLINIC-005' WHERE BusinessKey=N'CLINIC-003';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-CLINIC-005',N'Open',N'Synthetic pilot defect for PAT-6605',N'EVAL-CLINIC-005');
COMMIT;
GO

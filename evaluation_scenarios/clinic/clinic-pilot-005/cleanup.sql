SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-CLINIC-005';
UPDATE eval.[patients] SET BusinessKey=N'CLINIC-003',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-CLINIC' WHERE BusinessKey=N'PAT-6605' AND CorrelationId=N'EVAL-CLINIC-005';
COMMIT;
GO

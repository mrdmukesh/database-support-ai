SET XACT_ABORT ON;
BEGIN TRANSACTION;
DELETE FROM eval.exceptions WHERE CorrelationId=N'EVAL-CLINIC-003';
UPDATE eval.[lab_results] SET BusinessKey=N'CLINIC-010',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-CLINIC' WHERE BusinessKey=N'LAB-4403' AND CorrelationId=N'EVAL-CLINIC-003';
COMMIT;
GO

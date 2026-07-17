SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[time_entries] SET BusinessKey=N'TIME-8821',Status=N'Exception',Details=N'EVAL-PAYROLL-003',CorrelationId=N'EVAL-PAYROLL-003' WHERE BusinessKey=N'PAYROLL-006';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-PAYROLL-003',N'Open',N'Synthetic pilot defect for TIME-8821',N'EVAL-PAYROLL-003');
COMMIT;
GO

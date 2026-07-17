SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[payments] SET BusinessKey=N'PAY-7003',Status=N'Exception',Details=N'EVAL-PAYROLL-002',CorrelationId=N'EVAL-PAYROLL-002' WHERE BusinessKey=N'PAYROLL-011';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-PAYROLL-002',N'Open',N'Synthetic pilot defect for PAY-7003',N'EVAL-PAYROLL-002');
COMMIT;
GO

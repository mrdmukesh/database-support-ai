SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[employees] SET BusinessKey=N'EMP-1042',Status=N'Exception',Details=N'EVAL-PAYROLL-001',CorrelationId=N'EVAL-PAYROLL-001' WHERE BusinessKey=N'PAYROLL-002';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-PAYROLL-001',N'Open',N'Synthetic pilot defect for EMP-1042',N'EVAL-PAYROLL-001');
COMMIT;
GO

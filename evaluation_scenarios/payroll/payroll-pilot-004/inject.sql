SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[payroll_runs] SET BusinessKey=N'RUN-2026-07-A',Status=N'Exception',Details=N'EVAL-PAYROLL-004',CorrelationId=N'EVAL-PAYROLL-004' WHERE BusinessKey=N'PAYROLL-008';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-PAYROLL-004',N'Open',N'Synthetic pilot defect for RUN-2026-07-A',N'EVAL-PAYROLL-004');
COMMIT;
GO

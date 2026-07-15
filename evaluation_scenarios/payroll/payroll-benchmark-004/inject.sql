SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[time_entries](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0004-A',N'Failed',N'missing downstream record',N'EVAL-PAYROLL-104');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0004-A',N'Open',N'Primary synthetic defect: missing downstream record',N'EVAL-PAYROLL-104');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0004-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-104');
COMMIT;
GO

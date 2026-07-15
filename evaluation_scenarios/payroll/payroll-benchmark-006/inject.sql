SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[employees](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0006-A',N'Failed',N'workflow interruption',N'EVAL-PAYROLL-106');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0006-A',N'Failed',N'workflow interruption evidence',N'EVAL-PAYROLL-106');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0006-A',N'Open',N'Primary synthetic defect: workflow interruption',N'EVAL-PAYROLL-106');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0006-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-106');
COMMIT;
GO

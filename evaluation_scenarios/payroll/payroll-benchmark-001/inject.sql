SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payroll_runs](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0001-A',N'Failed',N'exact entity lookup',N'EVAL-PAYROLL-101');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0001-A',N'Failed',N'exact entity lookup evidence',N'EVAL-PAYROLL-101');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0001-A',N'Open',N'Primary synthetic defect: exact entity lookup',N'EVAL-PAYROLL-101');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0001-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-101');
COMMIT;
GO

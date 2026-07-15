SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payroll_runs](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0009-A',N'Failed',N'queue backlog',N'EVAL-PAYROLL-109');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0009-A',N'Failed',N'queue backlog evidence',N'EVAL-PAYROLL-109');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0009-A',N'Open',N'Primary synthetic defect: queue backlog',N'EVAL-PAYROLL-109');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0009-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-109');
COMMIT;
GO

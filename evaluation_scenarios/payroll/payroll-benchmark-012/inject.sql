SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[time_entries](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0012-A',N'Failed',N'missing reference data',N'EVAL-PAYROLL-112');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0012-A',N'Failed',N'missing reference data evidence',N'EVAL-PAYROLL-112');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0012-A',N'Open',N'Primary synthetic defect: missing reference data',N'EVAL-PAYROLL-112');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0012-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-112');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[time_entries](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0020-A',N'Failed',N'multi table investigation',N'EVAL-PAYROLL-120');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0020-A',N'Failed',N'multi table investigation evidence',N'EVAL-PAYROLL-120');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0020-A',N'Open',N'Primary synthetic defect: multi table investigation',N'EVAL-PAYROLL-120');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0020-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-120');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0011-A',N'Failed',N'audit history inconsistency',N'EVAL-PAYROLL-111');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0011-A',N'Failed',N'audit history inconsistency evidence',N'EVAL-PAYROLL-111');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0011-A',N'Open',N'Primary synthetic defect: audit history inconsistency',N'EVAL-PAYROLL-111');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0011-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-111');
COMMIT;
GO

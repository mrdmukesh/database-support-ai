SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payroll_items](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0010-A',N'Failed',N'retry failure',N'EVAL-PAYROLL-110');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0010-A',N'Failed',N'retry failure evidence',N'EVAL-PAYROLL-110');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0010-A',N'Open',N'Primary synthetic defect: retry failure',N'EVAL-PAYROLL-110');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0010-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-110');
COMMIT;
GO

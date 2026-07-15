SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[employees](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0014-A',N'Failed',N'trigger failure',N'EVAL-PAYROLL-114');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0014-A',N'Failed',N'trigger failure evidence',N'EVAL-PAYROLL-114');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0014-A',N'Open',N'Primary synthetic defect: trigger failure',N'EVAL-PAYROLL-114');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0014-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-114');
COMMIT;
GO

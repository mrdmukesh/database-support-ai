SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[leave_requests](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0008-A',N'Failed',N'integration failure',N'EVAL-PAYROLL-108');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0008-A',N'Failed',N'integration failure evidence',N'EVAL-PAYROLL-108');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0008-A',N'Open',N'Primary synthetic defect: integration failure',N'EVAL-PAYROLL-108');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0008-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-108');
COMMIT;
GO

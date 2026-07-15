SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[deductions](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0013-A',N'Failed',N'stored procedure defect',N'EVAL-PAYROLL-113');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0013-A',N'Failed',N'stored procedure defect evidence',N'EVAL-PAYROLL-113');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0013-A',N'Open',N'Primary synthetic defect: stored procedure defect',N'EVAL-PAYROLL-113');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0013-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-113');
COMMIT;
GO

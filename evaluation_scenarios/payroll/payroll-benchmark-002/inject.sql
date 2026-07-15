SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payroll_items](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0002-A',N'Failed',N'partial entity resolution',N'EVAL-PAYROLL-102');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0002-A',N'Failed',N'partial entity resolution evidence',N'EVAL-PAYROLL-102');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0002-A',N'Open',N'Primary synthetic defect: partial entity resolution',N'EVAL-PAYROLL-102');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0002-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-102');
COMMIT;
GO

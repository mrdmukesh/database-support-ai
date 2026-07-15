SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[tax_filings](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0007-A',N'Failed',N'exception handling',N'EVAL-PAYROLL-107');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0007-A',N'Failed',N'exception handling evidence',N'EVAL-PAYROLL-107');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0007-A',N'Open',N'Primary synthetic defect: exception handling',N'EVAL-PAYROLL-107');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0007-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-107');
COMMIT;
GO

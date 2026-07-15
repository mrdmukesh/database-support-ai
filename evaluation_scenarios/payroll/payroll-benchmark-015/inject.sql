SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[tax_filings](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0015-A',N'Failed',N'batch processing failure',N'EVAL-PAYROLL-115');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0015-A',N'Failed',N'batch processing failure evidence',N'EVAL-PAYROLL-115');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0015-A',N'Open',N'Primary synthetic defect: batch processing failure',N'EVAL-PAYROLL-115');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0015-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-115');
COMMIT;
GO

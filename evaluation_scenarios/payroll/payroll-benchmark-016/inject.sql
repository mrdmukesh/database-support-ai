SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[leave_requests](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0016-A',N'Failed',N'concurrency race condition',N'EVAL-PAYROLL-116');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0016-A',N'Failed',N'concurrency race condition evidence',N'EVAL-PAYROLL-116');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0016-A',N'Open',N'Primary synthetic defect: concurrency race condition',N'EVAL-PAYROLL-116');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0016-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-116');
COMMIT;
GO

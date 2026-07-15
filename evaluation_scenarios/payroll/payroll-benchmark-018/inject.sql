SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payroll_items](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0018-A',N'Failed',N'idempotency issue',N'EVAL-PAYROLL-118');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0018-A',N'Failed',N'idempotency issue evidence',N'EVAL-PAYROLL-118');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0018-A',N'Open',N'Primary synthetic defect: idempotency issue',N'EVAL-PAYROLL-118');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0018-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-118');
COMMIT;
GO

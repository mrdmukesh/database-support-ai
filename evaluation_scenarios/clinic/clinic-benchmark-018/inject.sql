SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[encounters](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0018-A',N'Failed',N'idempotency issue',N'EVAL-CLINIC-118');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0018-A',N'Failed',N'idempotency issue evidence',N'EVAL-CLINIC-118');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0018-A',N'Open',N'Primary synthetic defect: idempotency issue',N'EVAL-CLINIC-118');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0018-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-118');
COMMIT;
GO

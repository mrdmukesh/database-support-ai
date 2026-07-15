SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transfers](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0018-A',N'Failed',N'idempotency issue',N'EVAL-BANKING-118');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0018-A',N'Failed',N'idempotency issue evidence',N'EVAL-BANKING-118');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0018-A',N'Open',N'Primary synthetic defect: idempotency issue',N'EVAL-BANKING-118');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0018-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-118');
COMMIT;
GO

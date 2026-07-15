SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[fraud_alerts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0016-A',N'Failed',N'concurrency race condition',N'EVAL-BANKING-116');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0016-A',N'Failed',N'concurrency race condition evidence',N'EVAL-BANKING-116');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0016-A',N'Open',N'Primary synthetic defect: concurrency race condition',N'EVAL-BANKING-116');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0016-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-116');
COMMIT;
GO

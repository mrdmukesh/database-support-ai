SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[bills_of_lading](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0016-A',N'Failed',N'concurrency race condition',N'EVAL-SHIPPING-116');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0016-A',N'Failed',N'concurrency race condition evidence',N'EVAL-SHIPPING-116');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0016-A',N'Open',N'Primary synthetic defect: concurrency race condition',N'EVAL-SHIPPING-116');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0016-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-116');
COMMIT;
GO

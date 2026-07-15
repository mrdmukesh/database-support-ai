SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transactions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0009-A',N'Failed',N'queue backlog',N'EVAL-BANKING-109');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0009-A',N'Failed',N'queue backlog evidence',N'EVAL-BANKING-109');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0009-A',N'Open',N'Primary synthetic defect: queue backlog',N'EVAL-BANKING-109');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0009-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-109');
COMMIT;
GO

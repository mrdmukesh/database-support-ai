SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[accounts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0012-A',N'Failed',N'missing reference data',N'EVAL-BANKING-112');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0012-A',N'Failed',N'missing reference data evidence',N'EVAL-BANKING-112');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0012-A',N'Open',N'Primary synthetic defect: missing reference data',N'EVAL-BANKING-112');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0012-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-112');
COMMIT;
GO

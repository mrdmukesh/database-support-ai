SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[fraud_alerts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0008-A',N'Failed',N'integration failure',N'EVAL-BANKING-108');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0008-A',N'Failed',N'integration failure evidence',N'EVAL-BANKING-108');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0008-A',N'Open',N'Primary synthetic defect: integration failure',N'EVAL-BANKING-108');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0008-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-108');
COMMIT;
GO

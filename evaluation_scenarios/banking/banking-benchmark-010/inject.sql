SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transfers](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0010-A',N'Failed',N'retry failure',N'EVAL-BANKING-110');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0010-A',N'Failed',N'retry failure evidence',N'EVAL-BANKING-110');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0010-A',N'Open',N'Primary synthetic defect: retry failure',N'EVAL-BANKING-110');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0010-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-110');
COMMIT;
GO

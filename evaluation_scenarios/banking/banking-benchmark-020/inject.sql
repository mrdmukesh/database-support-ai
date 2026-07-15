SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[accounts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0020-A',N'Failed',N'multi table investigation',N'EVAL-BANKING-120');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0020-A',N'Failed',N'multi table investigation evidence',N'EVAL-BANKING-120');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0020-A',N'Open',N'Primary synthetic defect: multi table investigation',N'EVAL-BANKING-120');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0020-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-120');
COMMIT;
GO

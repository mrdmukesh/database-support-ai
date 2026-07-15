SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transfers](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0002-A',N'Failed',N'partial entity resolution',N'EVAL-BANKING-102');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0002-A',N'Failed',N'partial entity resolution evidence',N'EVAL-BANKING-102');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0002-A',N'Open',N'Primary synthetic defect: partial entity resolution',N'EVAL-BANKING-102');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0002-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-102');
COMMIT;
GO

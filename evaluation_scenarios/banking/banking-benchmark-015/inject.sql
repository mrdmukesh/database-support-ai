SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[cards](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0015-A',N'Failed',N'batch processing failure',N'EVAL-BANKING-115');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0015-A',N'Failed',N'batch processing failure evidence',N'EVAL-BANKING-115');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0015-A',N'Open',N'Primary synthetic defect: batch processing failure',N'EVAL-BANKING-115');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0015-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-115');
COMMIT;
GO

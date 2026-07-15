SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[loans](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0006-A',N'Failed',N'workflow interruption',N'EVAL-BANKING-106');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0006-A',N'Failed',N'workflow interruption evidence',N'EVAL-BANKING-106');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0006-A',N'Open',N'Primary synthetic defect: workflow interruption',N'EVAL-BANKING-106');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0006-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-106');
COMMIT;
GO

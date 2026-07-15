SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[beneficiaries](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0005-A',N'Failed',N'duplicate transaction',N'EVAL-BANKING-105');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0005-A',N'Failed',N'duplicate transaction evidence',N'EVAL-BANKING-105');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0005-A',N'Open',N'Primary synthetic defect: duplicate transaction',N'EVAL-BANKING-105');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0005-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-105');
COMMIT;
GO

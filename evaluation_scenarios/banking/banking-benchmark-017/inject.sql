SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transactions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0017-A',N'Failed',N'transaction rollback',N'EVAL-BANKING-117');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0017-A',N'Failed',N'transaction rollback evidence',N'EVAL-BANKING-117');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0017-A',N'Open',N'Primary synthetic defect: transaction rollback',N'EVAL-BANKING-117');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0017-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-117');
COMMIT;
GO

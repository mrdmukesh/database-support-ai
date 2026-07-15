SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[accounts](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0004-A',N'Failed',N'missing downstream record',N'EVAL-BANKING-104');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0004-A',N'Open',N'Primary synthetic defect: missing downstream record',N'EVAL-BANKING-104');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0004-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-104');
COMMIT;
GO

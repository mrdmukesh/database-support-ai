SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[beneficiaries](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0013-A',N'Failed',N'stored procedure defect',N'EVAL-BANKING-113');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0013-A',N'Failed',N'stored procedure defect evidence',N'EVAL-BANKING-113');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0013-A',N'Open',N'Primary synthetic defect: stored procedure defect',N'EVAL-BANKING-113');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0013-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-113');
COMMIT;
GO

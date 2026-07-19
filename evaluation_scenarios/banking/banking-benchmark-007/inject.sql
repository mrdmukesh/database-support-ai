SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[cards](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0007-A',N'Processing',N'exception handling',N'EVAL-BANKING-107');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0007-A',N'Failed',N'exception handling evidence',N'EVAL-BANKING-107');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0007-A',N'Open',N'Primary synthetic defect: exception handling',N'EVAL-BANKING-107');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0007-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-107');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transactions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0001-A',N'Failed',N'exact entity lookup',N'EVAL-BANKING-101');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0001-A',N'Failed',N'exact entity lookup evidence',N'EVAL-BANKING-101');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0001-A',N'Open',N'Primary synthetic defect: exact entity lookup',N'EVAL-BANKING-101');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0001-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-101');
COMMIT;
GO

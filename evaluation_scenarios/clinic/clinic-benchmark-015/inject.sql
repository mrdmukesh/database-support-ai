SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0015-A',N'Failed',N'batch processing failure',N'EVAL-CLINIC-115');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0015-A',N'Failed',N'batch processing failure evidence',N'EVAL-CLINIC-115');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0015-A',N'Open',N'Primary synthetic defect: batch processing failure',N'EVAL-CLINIC-115');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0015-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-115');
COMMIT;
GO

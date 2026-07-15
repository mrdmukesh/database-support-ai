SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[claims](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0011-A',N'Failed',N'audit history inconsistency',N'EVAL-CLINIC-111');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0011-A',N'Failed',N'audit history inconsistency evidence',N'EVAL-CLINIC-111');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0011-A',N'Open',N'Primary synthetic defect: audit history inconsistency',N'EVAL-CLINIC-111');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0011-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-111');
COMMIT;
GO

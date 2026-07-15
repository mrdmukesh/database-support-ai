SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_assignments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0011-A',N'Failed',N'audit history inconsistency',N'EVAL-SHIPPING-111');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0011-A',N'Failed',N'audit history inconsistency evidence',N'EVAL-SHIPPING-111');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0011-A',N'Open',N'Primary synthetic defect: audit history inconsistency',N'EVAL-SHIPPING-111');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0011-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-111');
COMMIT;
GO

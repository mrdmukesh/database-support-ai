SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_events](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0004-A',N'Failed',N'missing downstream record',N'EVAL-SHIPPING-104');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0004-A',N'Open',N'Primary synthetic defect: missing downstream record',N'EVAL-SHIPPING-104');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0004-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-104');
COMMIT;
GO

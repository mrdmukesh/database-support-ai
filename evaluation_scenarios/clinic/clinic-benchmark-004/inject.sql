SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[lab_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0004-A',N'Failed',N'missing downstream record',N'EVAL-CLINIC-104');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0004-A',N'Open',N'Primary synthetic defect: missing downstream record',N'EVAL-CLINIC-104');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0004-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-104');
COMMIT;
GO

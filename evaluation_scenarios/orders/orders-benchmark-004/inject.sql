SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[pick_tasks](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0004-A',N'Failed',N'missing downstream record',N'EVAL-ORDERS-104');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0004-A',N'Open',N'Primary synthetic defect: missing downstream record',N'EVAL-ORDERS-104');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0004-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-104');
COMMIT;
GO

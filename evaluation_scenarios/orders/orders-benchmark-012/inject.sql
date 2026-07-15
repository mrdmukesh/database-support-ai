SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[pick_tasks](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0012-A',N'Failed',N'missing reference data',N'EVAL-ORDERS-112');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0012-A',N'Failed',N'missing reference data evidence',N'EVAL-ORDERS-112');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0012-A',N'Open',N'Primary synthetic defect: missing reference data',N'EVAL-ORDERS-112');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0012-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-112');
COMMIT;
GO

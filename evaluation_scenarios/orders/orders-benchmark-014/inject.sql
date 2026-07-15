SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[inventory_movements](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0014-A',N'Failed',N'trigger failure',N'EVAL-ORDERS-114');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0014-A',N'Failed',N'trigger failure evidence',N'EVAL-ORDERS-114');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0014-A',N'Open',N'Primary synthetic defect: trigger failure',N'EVAL-ORDERS-114');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0014-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-114');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0009-A',N'Failed',N'queue backlog',N'EVAL-ORDERS-109');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0009-A',N'Failed',N'queue backlog evidence',N'EVAL-ORDERS-109');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0009-A',N'Open',N'Primary synthetic defect: queue backlog',N'EVAL-ORDERS-109');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0009-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-109');
COMMIT;
GO

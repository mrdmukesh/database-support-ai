SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0001-A',N'Failed',N'exact entity lookup',N'EVAL-ORDERS-101');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0001-A',N'Failed',N'exact entity lookup evidence',N'EVAL-ORDERS-101');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0001-A',N'Open',N'Primary synthetic defect: exact entity lookup',N'EVAL-ORDERS-101');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0001-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-101');
COMMIT;
GO

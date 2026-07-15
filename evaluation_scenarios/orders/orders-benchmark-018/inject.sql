SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_order_lines](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0018-A',N'Failed',N'idempotency issue',N'EVAL-ORDERS-118');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0018-A',N'Failed',N'idempotency issue evidence',N'EVAL-ORDERS-118');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0018-A',N'Open',N'Primary synthetic defect: idempotency issue',N'EVAL-ORDERS-118');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0018-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-118');
COMMIT;
GO

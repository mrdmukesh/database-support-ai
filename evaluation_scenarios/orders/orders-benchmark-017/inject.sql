SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0017-A',N'Failed',N'transaction rollback',N'EVAL-ORDERS-117');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0017-A',N'Failed',N'transaction rollback evidence',N'EVAL-ORDERS-117');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0017-A',N'Open',N'Primary synthetic defect: transaction rollback',N'EVAL-ORDERS-117');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0017-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-117');
COMMIT;
GO

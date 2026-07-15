SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_order_lines](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0010-A',N'Failed',N'retry failure',N'EVAL-ORDERS-110');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0010-A',N'Failed',N'retry failure evidence',N'EVAL-ORDERS-110');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0010-A',N'Open',N'Primary synthetic defect: retry failure',N'EVAL-ORDERS-110');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0010-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-110');
COMMIT;
GO

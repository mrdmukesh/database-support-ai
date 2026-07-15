SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[sales_order_lines](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0002-A',N'Failed',N'partial entity resolution',N'EVAL-ORDERS-102');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0002-A',N'Failed',N'partial entity resolution evidence',N'EVAL-ORDERS-102');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0002-A',N'Open',N'Primary synthetic defect: partial entity resolution',N'EVAL-ORDERS-102');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0002-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-102');
COMMIT;
GO

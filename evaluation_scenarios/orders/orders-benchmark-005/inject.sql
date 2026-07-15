SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0005-A',N'Failed',N'duplicate transaction',N'EVAL-ORDERS-105');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0005-A',N'Failed',N'duplicate transaction evidence',N'EVAL-ORDERS-105');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0005-A',N'Open',N'Primary synthetic defect: duplicate transaction',N'EVAL-ORDERS-105');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0005-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-105');
COMMIT;
GO

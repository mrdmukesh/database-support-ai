SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[purchase_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0008-A',N'Failed',N'integration failure',N'EVAL-ORDERS-108');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0008-A',N'Failed',N'integration failure evidence',N'EVAL-ORDERS-108');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0008-A',N'Open',N'Primary synthetic defect: integration failure',N'EVAL-ORDERS-108');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0008-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-108');
COMMIT;
GO

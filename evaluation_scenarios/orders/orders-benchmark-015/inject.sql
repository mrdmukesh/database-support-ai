SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[receipts](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0015-A',N'Failed',N'batch processing failure',N'EVAL-ORDERS-115');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0015-A',N'Failed',N'batch processing failure evidence',N'EVAL-ORDERS-115');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0015-A',N'Open',N'Primary synthetic defect: batch processing failure',N'EVAL-ORDERS-115');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0015-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-115');
COMMIT;
GO

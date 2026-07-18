SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[receipts](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0007-A',N'Processing',N'exception handling',N'EVAL-ORDERS-107');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0007-A',N'Failed',N'exception handling evidence',N'EVAL-ORDERS-107');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0007-A',N'Open',N'Primary synthetic defect: exception handling',N'EVAL-ORDERS-107');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0007-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-107');
COMMIT;
GO

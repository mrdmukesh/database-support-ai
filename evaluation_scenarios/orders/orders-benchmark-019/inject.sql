SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[allocations](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0019-A',N'Failed',N'incorrect business status',N'EVAL-ORDERS-119');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0019-A',N'Failed',N'incorrect business status evidence',N'EVAL-ORDERS-119');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0019-A',N'Open',N'Primary synthetic defect: incorrect business status',N'EVAL-ORDERS-119');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0019-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-119');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[allocations](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0011-A',N'Failed',N'audit history inconsistency',N'EVAL-ORDERS-111');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0011-A',N'Failed',N'audit history inconsistency evidence',N'EVAL-ORDERS-111');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0011-A',N'Open',N'Primary synthetic defect: audit history inconsistency',N'EVAL-ORDERS-111');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0011-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-111');
COMMIT;
GO

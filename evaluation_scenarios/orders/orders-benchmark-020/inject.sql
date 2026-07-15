SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[pick_tasks](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0020-A',N'Failed',N'multi table investigation',N'EVAL-ORDERS-120');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0020-A',N'Failed',N'multi table investigation evidence',N'EVAL-ORDERS-120');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0020-A',N'Open',N'Primary synthetic defect: multi table investigation',N'EVAL-ORDERS-120');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0020-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-120');
COMMIT;
GO

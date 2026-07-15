SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0013-A',N'Failed',N'stored procedure defect',N'EVAL-ORDERS-113');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0013-A',N'Failed',N'stored procedure defect evidence',N'EVAL-ORDERS-113');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0013-A',N'Open',N'Primary synthetic defect: stored procedure defect',N'EVAL-ORDERS-113');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0013-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-113');
COMMIT;
GO

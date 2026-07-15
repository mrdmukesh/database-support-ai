SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[transport_work_orders](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0014-A',N'Failed',N'trigger failure',N'EVAL-SHIPPING-114');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0014-A',N'Failed',N'trigger failure evidence',N'EVAL-SHIPPING-114');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0014-A',N'Open',N'Primary synthetic defect: trigger failure',N'EVAL-SHIPPING-114');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0014-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-114');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_events](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0020-A',N'Failed',N'multi table investigation',N'EVAL-SHIPPING-120');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0020-A',N'Failed',N'multi table investigation evidence',N'EVAL-SHIPPING-120');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0020-A',N'Open',N'Primary synthetic defect: multi table investigation',N'EVAL-SHIPPING-120');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0020-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-120');
COMMIT;
GO

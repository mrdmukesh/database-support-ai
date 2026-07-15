SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0001-A',N'Failed',N'exact entity lookup',N'EVAL-SHIPPING-101');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0001-A',N'Failed',N'exact entity lookup evidence',N'EVAL-SHIPPING-101');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0001-A',N'Open',N'Primary synthetic defect: exact entity lookup',N'EVAL-SHIPPING-101');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0001-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-101');
COMMIT;
GO

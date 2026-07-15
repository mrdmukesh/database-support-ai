SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipment_milestones](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0013-A',N'Failed',N'stored procedure defect',N'EVAL-SHIPPING-113');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0013-A',N'Failed',N'stored procedure defect evidence',N'EVAL-SHIPPING-113');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0013-A',N'Open',N'Primary synthetic defect: stored procedure defect',N'EVAL-SHIPPING-113');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0013-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-113');
COMMIT;
GO

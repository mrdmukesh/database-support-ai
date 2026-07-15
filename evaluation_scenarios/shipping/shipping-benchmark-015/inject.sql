SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[voyages](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0015-A',N'Failed',N'batch processing failure',N'EVAL-SHIPPING-115');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0015-A',N'Failed',N'batch processing failure evidence',N'EVAL-SHIPPING-115');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0015-A',N'Open',N'Primary synthetic defect: batch processing failure',N'EVAL-SHIPPING-115');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0015-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-115');
COMMIT;
GO

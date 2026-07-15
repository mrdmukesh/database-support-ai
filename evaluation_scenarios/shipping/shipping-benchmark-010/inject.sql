SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[bookings](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0010-A',N'Failed',N'retry failure',N'EVAL-SHIPPING-110');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0010-A',N'Failed',N'retry failure evidence',N'EVAL-SHIPPING-110');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0010-A',N'Open',N'Primary synthetic defect: retry failure',N'EVAL-SHIPPING-110');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0010-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-110');
COMMIT;
GO

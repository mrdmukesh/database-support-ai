SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[bookings](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0002-A',N'Failed',N'partial entity resolution',N'EVAL-SHIPPING-102');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0002-A',N'Failed',N'partial entity resolution evidence',N'EVAL-SHIPPING-102');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0002-A',N'Open',N'Primary synthetic defect: partial entity resolution',N'EVAL-SHIPPING-102');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0002-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-102');
COMMIT;
GO

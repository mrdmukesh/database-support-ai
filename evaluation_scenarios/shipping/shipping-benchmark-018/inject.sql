SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[bookings](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0018-A',N'Failed',N'idempotency issue',N'EVAL-SHIPPING-118');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0018-A',N'Failed',N'idempotency issue evidence',N'EVAL-SHIPPING-118');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0018-A',N'Open',N'Primary synthetic defect: idempotency issue',N'EVAL-SHIPPING-118');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0018-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-118');
COMMIT;
GO

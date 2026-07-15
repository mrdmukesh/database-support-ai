SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_assignments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0019-A',N'Failed',N'incorrect business status',N'EVAL-SHIPPING-119');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0019-A',N'Failed',N'incorrect business status evidence',N'EVAL-SHIPPING-119');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0019-A',N'Open',N'Primary synthetic defect: incorrect business status',N'EVAL-SHIPPING-119');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0019-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-119');
COMMIT;
GO

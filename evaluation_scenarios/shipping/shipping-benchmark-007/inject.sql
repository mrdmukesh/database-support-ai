SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[voyages](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0007-A',N'Failed',N'exception handling',N'EVAL-SHIPPING-107');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0007-A',N'Failed',N'exception handling evidence',N'EVAL-SHIPPING-107');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0007-A',N'Open',N'Primary synthetic defect: exception handling',N'EVAL-SHIPPING-107');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0007-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-107');
COMMIT;
GO

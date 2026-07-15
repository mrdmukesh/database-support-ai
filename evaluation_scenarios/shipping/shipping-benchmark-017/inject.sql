SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[shipments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0017-A',N'Failed',N'transaction rollback',N'EVAL-SHIPPING-117');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0017-A',N'Failed',N'transaction rollback evidence',N'EVAL-SHIPPING-117');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0017-A',N'Open',N'Primary synthetic defect: transaction rollback',N'EVAL-SHIPPING-117');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0017-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-117');
COMMIT;
GO

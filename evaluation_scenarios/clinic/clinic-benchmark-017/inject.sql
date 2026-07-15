SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[appointments](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0017-A',N'Failed',N'transaction rollback',N'EVAL-CLINIC-117');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0017-A',N'Failed',N'transaction rollback evidence',N'EVAL-CLINIC-117');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0017-A',N'Open',N'Primary synthetic defect: transaction rollback',N'EVAL-CLINIC-117');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0017-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-117');
COMMIT;
GO

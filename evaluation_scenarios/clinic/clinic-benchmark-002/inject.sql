SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[encounters](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0002-A',N'Failed',N'partial entity resolution',N'EVAL-CLINIC-102');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0002-A',N'Failed',N'partial entity resolution evidence',N'EVAL-CLINIC-102');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0002-A',N'Open',N'Primary synthetic defect: partial entity resolution',N'EVAL-CLINIC-102');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0002-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-102');
COMMIT;
GO

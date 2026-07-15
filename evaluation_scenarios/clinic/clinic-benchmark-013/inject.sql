SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[lab_results](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0013-A',N'Failed',N'stored procedure defect',N'EVAL-CLINIC-113');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0013-A',N'Failed',N'stored procedure defect evidence',N'EVAL-CLINIC-113');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0013-A',N'Open',N'Primary synthetic defect: stored procedure defect',N'EVAL-CLINIC-113');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0013-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-113');
COMMIT;
GO

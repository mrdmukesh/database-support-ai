SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[claims](BusinessKey,Status,Details,CorrelationId) VALUES (N'CLN-2026-0003-A',N'Failed',N'Candidate A',N'EVAL-CLINIC-103'),(N'CLN-2026-0003-B',N'Failed',N'Candidate B',N'EVAL-CLINIC-103');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-CLN-2026-0003-A',N'Failed',N'ambiguous entity resolution evidence',N'EVAL-CLINIC-103');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-CLN-2026-0003-A',N'Open',N'Primary synthetic defect: ambiguous entity resolution',N'EVAL-CLINIC-103');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-CLN-2026-0003-A',N'Recorded',N'Observed workflow state',N'EVAL-CLINIC-103');
COMMIT;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payment_instructions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0003-A',N'Failed',N'Candidate A',N'EVAL-BANKING-103'),(N'BNK-2026-0003-B',N'Failed',N'Candidate B',N'EVAL-BANKING-103');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0003-A',N'Failed',N'ambiguous entity resolution evidence',N'EVAL-BANKING-103');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0003-A',N'Open',N'Primary synthetic defect: ambiguous entity resolution',N'EVAL-BANKING-103');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0003-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-103');
COMMIT;
GO

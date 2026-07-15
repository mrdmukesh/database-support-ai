SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[container_assignments](BusinessKey,Status,Details,CorrelationId) VALUES (N'SHP-2026-0003-A',N'Failed',N'Candidate A',N'EVAL-SHIPPING-103'),(N'SHP-2026-0003-B',N'Failed',N'Candidate B',N'EVAL-SHIPPING-103');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-SHP-2026-0003-A',N'Failed',N'ambiguous entity resolution evidence',N'EVAL-SHIPPING-103');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-SHP-2026-0003-A',N'Open',N'Primary synthetic defect: ambiguous entity resolution',N'EVAL-SHIPPING-103');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-SHP-2026-0003-A',N'Recorded',N'Observed workflow state',N'EVAL-SHIPPING-103');
COMMIT;
GO

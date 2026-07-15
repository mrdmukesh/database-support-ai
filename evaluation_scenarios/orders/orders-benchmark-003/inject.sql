SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[allocations](BusinessKey,Status,Details,CorrelationId) VALUES (N'ORD-2026-0003-A',N'Failed',N'Candidate A',N'EVAL-ORDERS-103'),(N'ORD-2026-0003-B',N'Failed',N'Candidate B',N'EVAL-ORDERS-103');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-ORD-2026-0003-A',N'Failed',N'ambiguous entity resolution evidence',N'EVAL-ORDERS-103');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-ORD-2026-0003-A',N'Open',N'Primary synthetic defect: ambiguous entity resolution',N'EVAL-ORDERS-103');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-ORD-2026-0003-A',N'Recorded',N'Observed workflow state',N'EVAL-ORDERS-103');
COMMIT;
GO

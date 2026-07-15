SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payments](BusinessKey,Status,Details,CorrelationId) VALUES (N'PAY-2026-0003-A',N'Failed',N'Candidate A',N'EVAL-PAYROLL-103'),(N'PAY-2026-0003-B',N'Failed',N'Candidate B',N'EVAL-PAYROLL-103');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-PAY-2026-0003-A',N'Failed',N'ambiguous entity resolution evidence',N'EVAL-PAYROLL-103');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-PAY-2026-0003-A',N'Open',N'Primary synthetic defect: ambiguous entity resolution',N'EVAL-PAYROLL-103');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-PAY-2026-0003-A',N'Recorded',N'Observed workflow state',N'EVAL-PAYROLL-103');
COMMIT;
GO

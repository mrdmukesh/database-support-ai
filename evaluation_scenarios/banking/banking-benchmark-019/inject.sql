SET XACT_ABORT ON;
BEGIN TRANSACTION;
INSERT eval.[payment_instructions](BusinessKey,Status,Details,CorrelationId) VALUES (N'BNK-2026-0019-A',N'Failed',N'incorrect business status',N'EVAL-BANKING-119');
INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES (N'MSG-BNK-2026-0019-A',N'Failed',N'incorrect business status evidence',N'EVAL-BANKING-119');
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EX-BNK-2026-0019-A',N'Open',N'Primary synthetic defect: incorrect business status',N'EVAL-BANKING-119');
INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) VALUES (N'AUD-BNK-2026-0019-A',N'Recorded',N'Observed workflow state',N'EVAL-BANKING-119');
COMMIT;
GO

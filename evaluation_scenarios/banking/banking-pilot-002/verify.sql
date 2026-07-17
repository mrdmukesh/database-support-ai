SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payment_instructions] WHERE BusinessKey=N'PMT-3102') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[payment_instructions] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PMT-3102' AND e.CorrelationId=N'EVAL-BANKING-002' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.payment_instructions' EntityTable,N'BusinessKey' EntityColumn,N'PMT-3102' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[payment_instructions] WHERE BusinessKey=N'PMT-3102';
GO

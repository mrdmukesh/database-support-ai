SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[transactions] WHERE BusinessKey=N'TXN-3105') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[transactions] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'TXN-3105' AND e.CorrelationId=N'EVAL-BANKING-005' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.transactions' EntityTable,N'BusinessKey' EntityColumn,N'TXN-3105' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[transactions] WHERE BusinessKey=N'TXN-3105';
GO

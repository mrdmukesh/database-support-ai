SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[accounts] WHERE BusinessKey=N'ACC-3103') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[accounts] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ACC-3103' AND e.CorrelationId=N'EVAL-BANKING-003' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.accounts' EntityTable,N'BusinessKey' EntityColumn,N'ACC-3103' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[accounts] WHERE BusinessKey=N'ACC-3103';
GO

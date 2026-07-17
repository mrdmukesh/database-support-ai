SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[products] WHERE BusinessKey=N'SKU-8103') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[products] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'SKU-8103' AND e.CorrelationId=N'EVAL-ORDERS-003' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.products' EntityTable,N'BusinessKey' EntityColumn,N'SKU-8103' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[products] WHERE BusinessKey=N'SKU-8103';
GO

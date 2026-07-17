SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[sales_orders] WHERE BusinessKey=N'ORD-7102') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[sales_orders] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ORD-7102' AND e.CorrelationId=N'EVAL-ORDERS-002' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.sales_orders' EntityTable,N'BusinessKey' EntityColumn,N'ORD-7102' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[sales_orders] WHERE BusinessKey=N'ORD-7102';
GO

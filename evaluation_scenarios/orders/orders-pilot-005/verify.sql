SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[purchase_orders] WHERE BusinessKey=N'PO-1205') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[purchase_orders] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PO-1205' AND e.CorrelationId=N'EVAL-ORDERS-005' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.purchase_orders' EntityTable,N'BusinessKey' EntityColumn,N'PO-1205' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[purchase_orders] WHERE BusinessKey=N'PO-1205';
GO

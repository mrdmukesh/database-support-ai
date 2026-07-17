SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[pick_tasks] WHERE BusinessKey=N'PICK-9104') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[pick_tasks] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PICK-9104' AND e.CorrelationId=N'EVAL-ORDERS-004' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.pick_tasks' EntityTable,N'BusinessKey' EntityColumn,N'PICK-9104' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[pick_tasks] WHERE BusinessKey=N'PICK-9104';
GO

SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[batch_runs] WHERE BusinessKey=N'BAT-3104' AND Status=N'Running') <> 1 THROW 51021, 'Exact expected entity/status missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[batch_runs] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'BAT-3104' AND e.CorrelationId=N'EVAL-BANKING-004' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.batch_runs' EntityTable,N'BusinessKey' EntityColumn,N'BAT-3104' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[batch_runs] WHERE BusinessKey=N'BAT-3104';
GO

SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[transfers] WHERE BusinessKey=N'TRF-3101') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[transfers] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'TRF-3101' AND e.CorrelationId=N'EVAL-BANKING-001' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.transfers' EntityTable,N'BusinessKey' EntityColumn,N'TRF-3101' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[transfers] WHERE BusinessKey=N'TRF-3101';
GO

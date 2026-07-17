SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[claims] WHERE BusinessKey=N'CLM-3302') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[claims] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'CLM-3302' AND e.CorrelationId=N'EVAL-CLINIC-002' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.claims' EntityTable,N'BusinessKey' EntityColumn,N'CLM-3302' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[claims] WHERE BusinessKey=N'CLM-3302';
GO

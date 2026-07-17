SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[encounters] WHERE BusinessKey=N'ENC-5504') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[encounters] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'ENC-5504' AND e.CorrelationId=N'EVAL-CLINIC-004' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.encounters' EntityTable,N'BusinessKey' EntityColumn,N'ENC-5504' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[encounters] WHERE BusinessKey=N'ENC-5504';
GO

SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[appointments] WHERE BusinessKey=N'APT-2101') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[appointments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'APT-2101' AND e.CorrelationId=N'EVAL-CLINIC-001' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.appointments' EntityTable,N'BusinessKey' EntityColumn,N'APT-2101' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[appointments] WHERE BusinessKey=N'APT-2101';
GO

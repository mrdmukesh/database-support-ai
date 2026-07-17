SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[patients] WHERE BusinessKey=N'PAT-6605') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[patients] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PAT-6605' AND e.CorrelationId=N'EVAL-CLINIC-005' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.patients' EntityTable,N'BusinessKey' EntityColumn,N'PAT-6605' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[patients] WHERE BusinessKey=N'PAT-6605';
GO

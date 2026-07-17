SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[time_entries] WHERE BusinessKey=N'TIME-8821') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[time_entries] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'TIME-8821' AND e.CorrelationId=N'EVAL-PAYROLL-003' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.time_entries' EntityTable,N'BusinessKey' EntityColumn,N'TIME-8821' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[time_entries] WHERE BusinessKey=N'TIME-8821';
GO

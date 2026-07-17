SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[employees] WHERE BusinessKey=N'EMP-1042') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[employees] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'EMP-1042' AND e.CorrelationId=N'EVAL-PAYROLL-001' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.employees' EntityTable,N'BusinessKey' EntityColumn,N'EMP-1042' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[employees] WHERE BusinessKey=N'EMP-1042';
GO

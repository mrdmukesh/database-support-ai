SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payments] WHERE BusinessKey=N'PAY-7003') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[payments] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'PAY-7003' AND e.CorrelationId=N'EVAL-PAYROLL-002' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.payments' EntityTable,N'BusinessKey' EntityColumn,N'PAY-7003' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[payments] WHERE BusinessKey=N'PAY-7003';
GO

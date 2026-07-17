SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM eval.[payroll_runs] WHERE BusinessKey=N'RUN-2026-07-A') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;
IF NOT EXISTS (SELECT 1 FROM eval.[payroll_runs] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'RUN-2026-07-A' AND e.CorrelationId=N'EVAL-PAYROLL-004' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;
SELECT N'ENTITY_FOUND' EntityStatus,N'eval.payroll_runs' EntityTable,N'BusinessKey' EntityColumn,N'RUN-2026-07-A' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[payroll_runs] WHERE BusinessKey=N'RUN-2026-07-A';
GO

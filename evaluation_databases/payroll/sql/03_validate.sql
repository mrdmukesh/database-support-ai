SET NOCOUNT ON;
IF EXISTS (SELECT 'departments' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[departments] UNION ALL SELECT 'employees' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[employees] UNION ALL SELECT 'employment_history' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[employment_history] ) BEGIN SELECT * FROM (SELECT 'departments' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[departments] UNION ALL SELECT 'employees' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[employees] UNION ALL SELECT 'employment_history' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[employment_history]) q; END;
IF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;
SELECT 'baseline_valid' ValidationStatus;
GO

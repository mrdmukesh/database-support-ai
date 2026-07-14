SET NOCOUNT ON;
IF EXISTS (SELECT 'customers' ObjectName, COUNT_BIG(*) RowCount FROM eval.[customers] UNION ALL SELECT 'accounts' ObjectName, COUNT_BIG(*) RowCount FROM eval.[accounts] UNION ALL SELECT 'account_balances' ObjectName, COUNT_BIG(*) RowCount FROM eval.[account_balances] ) BEGIN SELECT * FROM (SELECT 'customers' ObjectName, COUNT_BIG(*) RowCount FROM eval.[customers] UNION ALL SELECT 'accounts' ObjectName, COUNT_BIG(*) RowCount FROM eval.[accounts] UNION ALL SELECT 'account_balances' ObjectName, COUNT_BIG(*) RowCount FROM eval.[account_balances]) q; END;
IF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;
SELECT 'baseline_valid' ValidationStatus;
GO

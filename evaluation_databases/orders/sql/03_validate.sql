SET NOCOUNT ON;
IF EXISTS (SELECT 'customers' ObjectName, COUNT_BIG(*) RowCount FROM eval.[customers] UNION ALL SELECT 'products' ObjectName, COUNT_BIG(*) RowCount FROM eval.[products] UNION ALL SELECT 'warehouses' ObjectName, COUNT_BIG(*) RowCount FROM eval.[warehouses] ) BEGIN SELECT * FROM (SELECT 'customers' ObjectName, COUNT_BIG(*) RowCount FROM eval.[customers] UNION ALL SELECT 'products' ObjectName, COUNT_BIG(*) RowCount FROM eval.[products] UNION ALL SELECT 'warehouses' ObjectName, COUNT_BIG(*) RowCount FROM eval.[warehouses]) q; END;
IF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;
SELECT 'baseline_valid' ValidationStatus;
GO

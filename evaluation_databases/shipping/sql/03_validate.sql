SET NOCOUNT ON;
IF EXISTS (SELECT 'customers' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[customers] UNION ALL SELECT 'bookings' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[bookings] UNION ALL SELECT 'shipments' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[shipments] ) BEGIN SELECT * FROM (SELECT 'customers' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[customers] UNION ALL SELECT 'bookings' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[bookings] UNION ALL SELECT 'shipments' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[shipments]) q; END;
IF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;
SELECT 'baseline_valid' ValidationStatus;
GO

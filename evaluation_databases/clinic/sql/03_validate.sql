SET NOCOUNT ON;
IF EXISTS (SELECT 'clinics' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[clinics] UNION ALL SELECT 'providers' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[providers] UNION ALL SELECT 'patients' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[patients] ) BEGIN SELECT * FROM (SELECT 'clinics' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[clinics] UNION ALL SELECT 'providers' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[providers] UNION ALL SELECT 'patients' ObjectName, COUNT_BIG(*) [RowCount] FROM eval.[patients]) q; END;
IF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;
SELECT 'baseline_valid' ValidationStatus;
GO

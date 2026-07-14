DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-003'; UPDATE eval.[time_entries] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-PAYROLL-003';
GO

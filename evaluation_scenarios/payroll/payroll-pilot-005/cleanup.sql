DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-005'; UPDATE eval.[payroll_runs] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-PAYROLL-005';
GO

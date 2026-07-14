DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-002'; UPDATE eval.[pay_periods] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-PAYROLL-002';
GO

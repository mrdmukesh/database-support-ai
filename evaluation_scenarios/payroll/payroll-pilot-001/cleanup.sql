DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-001'; UPDATE eval.[pay_groups] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-PAYROLL-001';
GO

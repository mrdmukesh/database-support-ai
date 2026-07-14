DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-004'; UPDATE eval.[leave_requests] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-PAYROLL-004';
GO

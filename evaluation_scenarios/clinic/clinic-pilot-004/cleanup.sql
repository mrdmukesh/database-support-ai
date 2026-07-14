DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-004'; UPDATE eval.[procedures_performed] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-CLINIC-004';
GO

DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-005'; UPDATE eval.[prescriptions] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-CLINIC-005';
GO

DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-003'; UPDATE eval.[diagnoses] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-CLINIC-003';
GO

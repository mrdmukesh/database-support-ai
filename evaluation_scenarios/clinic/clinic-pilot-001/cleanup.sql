DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-001'; UPDATE eval.[appointments] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-CLINIC-001';
GO

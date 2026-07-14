DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-002'; UPDATE eval.[encounters] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-CLINIC-002';
GO

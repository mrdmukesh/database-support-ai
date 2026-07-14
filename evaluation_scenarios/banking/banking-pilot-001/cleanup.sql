DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-001'; UPDATE eval.[transactions] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-BANKING-001';
GO

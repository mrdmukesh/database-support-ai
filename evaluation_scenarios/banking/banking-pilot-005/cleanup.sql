DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-005'; UPDATE eval.[loans] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-BANKING-005';
GO

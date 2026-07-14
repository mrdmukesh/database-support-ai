DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-002'; UPDATE eval.[transfers] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-BANKING-002';
GO

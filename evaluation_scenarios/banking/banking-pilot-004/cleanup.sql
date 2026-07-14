DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-004'; UPDATE eval.[payment_instructions] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-BANKING-004';
GO

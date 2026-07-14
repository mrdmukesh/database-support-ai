DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-003'; UPDATE eval.[beneficiaries] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-BANKING-003';
GO

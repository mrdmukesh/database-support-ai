DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-005'; UPDATE eval.[allocations] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-ORDERS-005';
GO

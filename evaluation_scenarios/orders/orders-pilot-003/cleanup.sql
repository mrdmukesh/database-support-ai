DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-003'; UPDATE eval.[sales_orders] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-ORDERS-003';
GO

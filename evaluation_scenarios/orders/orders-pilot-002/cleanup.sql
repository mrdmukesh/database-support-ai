DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-002'; UPDATE eval.[inventory_movements] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-ORDERS-002';
GO

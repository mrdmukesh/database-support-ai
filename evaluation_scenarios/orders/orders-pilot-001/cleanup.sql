DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-001'; UPDATE eval.[inventory_balances] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-ORDERS-001';
GO

DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-004'; UPDATE eval.[sales_order_lines] SET Status='Active',Details='Synthetic baseline record' WHERE Details='EVAL-ORDERS-004';
GO

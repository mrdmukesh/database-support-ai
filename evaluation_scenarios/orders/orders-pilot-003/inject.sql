INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-ORDERS-003','Open','Synthetic pilot defect for SKU-8103','EVAL-ORDERS-003'); UPDATE eval.[sales_orders] SET Status='Exception',Details='EVAL-ORDERS-003' WHERE [SalesOrdersId]=1;
GO

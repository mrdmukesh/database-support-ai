INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-ORDERS-004','Open','Synthetic pilot defect for PICK-9104','EVAL-ORDERS-004'); UPDATE eval.[sales_order_lines] SET Status='Exception',Details='EVAL-ORDERS-004' WHERE [SalesOrderLinesId]=1;
GO

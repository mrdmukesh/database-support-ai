INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-ORDERS-001','Open','Synthetic pilot defect for ORD-7101','EVAL-ORDERS-001'); UPDATE eval.[inventory_balances] SET Status='Exception',Details='EVAL-ORDERS-001' WHERE [InventoryBalancesId]=1;
GO

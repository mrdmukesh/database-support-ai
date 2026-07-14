INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-ORDERS-002','Open','Synthetic pilot defect for ORD-7102','EVAL-ORDERS-002'); UPDATE eval.[inventory_movements] SET Status='Exception',Details='EVAL-ORDERS-002' WHERE [InventoryMovementsId]=1;
GO

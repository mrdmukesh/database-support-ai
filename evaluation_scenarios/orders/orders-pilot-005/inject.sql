INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-ORDERS-005','Open','Synthetic pilot defect for PO-1205','EVAL-ORDERS-005'); UPDATE eval.[allocations] SET Status='Exception',Details='EVAL-ORDERS-005' WHERE [AllocationsId]=1;
GO

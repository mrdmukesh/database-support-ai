DELETE FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001'; INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-SHIPPING-001','Open','Downstream empty-return creation absent','SHP-5001');
GO

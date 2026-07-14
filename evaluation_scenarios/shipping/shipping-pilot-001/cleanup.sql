DELETE FROM eval.exceptions WHERE CorrelationId='EVAL-SHIPPING-001'; INSERT eval.transport_work_orders(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'EMPTY-SHP-5001',ShipmentsId,'Completed','Empty return work order','SHIP-WF-1' FROM eval.shipments WHERE BusinessKey='SHP-5001' AND NOT EXISTS (SELECT 1 FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001');
GO

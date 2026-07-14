UPDATE eval.shipments SET Status='In Transit',CorrelationId='EVAL-SHIPPING-004' WHERE BusinessKey='SHP-5004'; INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES ('DISCHARGE-FAIL-SHP-5004','Failed','Discharge status update failed','EVAL-SHIPPING-004');
GO

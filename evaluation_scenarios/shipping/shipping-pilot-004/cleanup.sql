DELETE FROM eval.integration_messages WHERE CorrelationId='EVAL-SHIPPING-004'; UPDATE eval.shipments SET Status='Completed',CorrelationId='SHIP-WF-4' WHERE BusinessKey='SHP-5004';
GO

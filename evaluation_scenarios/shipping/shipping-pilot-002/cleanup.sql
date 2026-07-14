DELETE FROM eval.container_events WHERE CorrelationId='EVAL-SHIPPING-002'; CREATE UNIQUE INDEX UX_container_events_BusinessKey ON eval.container_events(BusinessKey);
GO

DROP INDEX UX_container_events_BusinessKey ON eval.container_events; INSERT eval.container_events(BusinessKey,ContainerAssignmentsId,Status,Details,CorrelationId) SELECT BusinessKey,ContainerAssignmentsId,Status,'Terminal retry copy','EVAL-SHIPPING-002' FROM eval.container_events WHERE BusinessKey='GATE-CONT-5002';
GO

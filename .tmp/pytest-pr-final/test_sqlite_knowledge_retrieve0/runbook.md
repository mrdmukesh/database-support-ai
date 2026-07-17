Module: gate
Business Object: event
Issue: duplicate
Duplicate GATE_IN events can happen when retry processing inserts without an idempotency key.
Procedure sp_retry_gate_events writes gate events.
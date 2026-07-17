# Retry Runbook

Appointment APT-2005 can create duplicate lab orders when retry processing lacks an idempotency guard.
Procedure sp_retry_failed_lab_orders writes lab_orders after checking appointment_number.
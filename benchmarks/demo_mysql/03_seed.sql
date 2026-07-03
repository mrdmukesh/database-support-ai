INSERT INTO patients (patient_number, patient_name) VALUES
('PAT-1001', 'Asha Rao'),
('PAT-1002', 'Brian Smith'),
('PAT-1003', 'Chen Li'),
('PAT-1004', 'Dina Patel');

INSERT INTO appointments (appointment_number, patient_id, appointment_status, checked_out_at, created_at) VALUES
('APT-2001', 1, 'CHECKED_OUT', '2026-06-27 10:00:00', '2026-06-27 09:00:00'),
('APT-2002', 2, 'CHECKED_OUT', '2026-06-27 11:00:00', '2026-06-27 10:15:00'),
('APT-2003', 3, 'SCHEDULED', NULL, '2026-06-27 10:30:00'),
('APT-2004', 4, 'CHECKED_OUT', '2026-06-27 14:00:00', '2026-06-27 13:00:00'),
('APT-2005', 3, 'CHECKED_OUT', '2026-06-27 15:00:00', '2026-06-27 14:20:00');

INSERT INTO lab_orders (
    appointment_id,
    patient_id,
    lab_order_number,
    lab_status,
    ordered_at,
    retry_source,
    created_at
) VALUES
(5, 3, 'LAB-2005-A', 'ORDERED', '2026-06-27 15:05:00', 'RETRY_JOB', '2026-07-02 13:46:30'),
(5, 3, 'LAB-2005-B', 'ORDERED', '2026-06-27 15:06:00', 'RETRY_JOB', '2026-07-02 13:46:30'),
(1, 1, 'LAB-2001-A', 'RESULTED', '2026-06-27 10:05:00', '', '2026-06-27 10:05:00');

INSERT INTO claims (appointment_id, claim_number, claim_status, created_at) VALUES
(1, 'CLM-2001', 'CREATED', '2026-06-27 12:00:00');

INSERT INTO batch_control (batch_name, batch_status, started_at, ended_at, error_count) VALUES
('Checked Out Appointment Processing', 'FAILED', '2026-07-02 01:00:00', '2026-07-02 01:35:00', 1),
('Claim Generation Batch', 'FAILED', '2026-07-02 02:00:00', '2026-07-02 02:10:00', 1);

INSERT INTO job_run_history (
    job_name,
    step_name,
    run_status,
    duration_seconds,
    procedure_name,
    error_message,
    created_at
) VALUES
('Lab Retry Job', 'Retry failed lab orders', 'COMPLETED_WITH_WARNINGS', 42, 'sp_retry_failed_lab_orders', 'Duplicate active lab order detected for APT-2005', '2026-07-02 13:46:30'),
('Checked Out Appointment Processing', 'Select checked out appointments', 'FAILED', 2100, 'sp_process_checked_out_appointments', 'Query exceeded SLA; non-SARGable DATE predicate', '2026-07-02 01:35:00'),
('Claim Generation Batch', 'Generate claims', 'FAILED', 600, 'sp_generate_claims', 'Claim blocked because active lab order exists for appointment', '2026-07-02 02:10:00');

INSERT INTO error_log (business_key, module_name, procedure_name, error_message, created_at) VALUES
('APT-2005', 'lab_orders', 'sp_retry_failed_lab_orders', 'DUPLICATE_LAB_ORDER: retry inserted another active lab order', '2026-07-02 13:46:30'),
('APT-2004', 'claims', 'sp_generate_claims', 'MISSING_CLAIM: claim generation failed after checked-out appointment', '2026-07-02 02:10:00'),
('Checked Out Appointment Processing', 'appointments', 'sp_process_checked_out_appointments', 'SLOW_QUERY: DATE(checked_out_at) prevents efficient index usage', '2026-07-02 01:35:00');

INSERT INTO ai_expected_issues (
    issue_id,
    question,
    business_key,
    affected_object,
    expected_root_cause,
    expected_procedure,
    expected_evidence,
    issue_type
) VALUES
(
    'DEMO-DUP-LAB-001',
    'Appointment APT-2005 created two active lab orders. Investigate affected object, parent object, write path, root cause, evidence, fix, tests, proof of fix, and rollback.',
    'APT-2005',
    'lab_orders',
    'Retry procedure creates active lab orders without idempotency or existing-active-child validation.',
    'sp_retry_failed_lab_orders',
    'Two ORDERED lab_orders exist for appointment APT-2005 and error/job history reference sp_retry_failed_lab_orders.',
    'duplicate'
),
(
    'DEMO-MISSING-CLAIM-001',
    'Appointment APT-2004 is checked out but claim is missing. Investigate missing child record and root cause.',
    'APT-2004',
    'claims',
    'Claim generation did not create the expected claim for a checked-out appointment; procedure/job evidence should explain the blocked child creation.',
    'sp_generate_claims',
    'Appointment APT-2004 has no claim row and Claim Generation Batch failed.',
    'missing_child'
),
(
    'DEMO-PERF-APPT-001',
    'Why is Checked Out Appointment Processing slow? Analyze EXPLAIN, indexes, row scans, stored procedure logic, and recommend optimization.',
    'Checked Out Appointment Processing',
    'appointments',
    'Stored procedure uses a non-SARGable DATE predicate and lacks a composite access path for status/time filtering.',
    'sp_process_checked_out_appointments',
    'Job history shows SLA failure and procedure logic contains DATE(checked_out_at).',
    'performance'
);

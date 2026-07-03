DROP TABLE IF EXISTS ai_expected_issues;
DROP TABLE IF EXISTS job_run_history;
DROP TABLE IF EXISTS batch_control;
DROP TABLE IF EXISTS error_log;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS lab_orders;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS patients;

CREATE TABLE patients (
    patient_id INT PRIMARY KEY AUTO_INCREMENT,
    patient_number VARCHAR(40) NOT NULL UNIQUE,
    patient_name VARCHAR(120) NOT NULL
);

CREATE TABLE appointments (
    appointment_id INT PRIMARY KEY AUTO_INCREMENT,
    appointment_number VARCHAR(40) NOT NULL UNIQUE,
    patient_id INT NOT NULL,
    appointment_status VARCHAR(40) NOT NULL,
    checked_out_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE lab_orders (
    lab_order_id INT PRIMARY KEY AUTO_INCREMENT,
    appointment_id INT NOT NULL,
    patient_id INT NOT NULL,
    lab_order_number VARCHAR(40) NOT NULL,
    lab_status VARCHAR(40) NOT NULL,
    ordered_at DATETIME NOT NULL,
    retry_source VARCHAR(40) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_lab_orders_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    CONSTRAINT fk_lab_orders_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE claims (
    claim_id INT PRIMARY KEY AUTO_INCREMENT,
    appointment_id INT NOT NULL,
    claim_number VARCHAR(40) NOT NULL UNIQUE,
    claim_status VARCHAR(40) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_claims_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

CREATE TABLE batch_control (
    batch_id INT PRIMARY KEY AUTO_INCREMENT,
    batch_name VARCHAR(120) NOT NULL,
    batch_status VARCHAR(40) NOT NULL,
    started_at DATETIME NULL,
    ended_at DATETIME NULL,
    error_count INT NOT NULL DEFAULT 0
);

CREATE TABLE job_run_history (
    job_run_id INT PRIMARY KEY AUTO_INCREMENT,
    job_name VARCHAR(120) NOT NULL,
    step_name VARCHAR(120) NOT NULL,
    run_status VARCHAR(40) NOT NULL,
    duration_seconds INT NOT NULL,
    procedure_name VARCHAR(120) NOT NULL,
    error_message TEXT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE error_log (
    error_id INT PRIMARY KEY AUTO_INCREMENT,
    business_key VARCHAR(80) NOT NULL,
    module_name VARCHAR(120) NOT NULL,
    procedure_name VARCHAR(120) NOT NULL,
    error_message TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE ai_expected_issues (
    issue_id VARCHAR(80) PRIMARY KEY,
    question TEXT NOT NULL,
    business_key VARCHAR(80) NOT NULL,
    affected_object VARCHAR(120) NOT NULL,
    expected_root_cause TEXT NOT NULL,
    expected_procedure VARCHAR(120) NOT NULL,
    expected_evidence TEXT NOT NULL,
    issue_type VARCHAR(80) NOT NULL
);

CREATE INDEX idx_appointments_status ON appointments(appointment_status);
CREATE INDEX idx_lab_orders_appointment ON lab_orders(appointment_id);
CREATE INDEX idx_claims_appointment ON claims(appointment_id);

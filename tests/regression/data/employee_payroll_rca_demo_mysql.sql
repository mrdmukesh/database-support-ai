
-- ============================================================
-- Fresh Employee Payroll RCA Demo Database
-- Engine: MySQL 8.0+
-- Purpose:
--   A self-contained schema for testing evidence-grounded
--   database investigations, metadata discovery, safe SQL,
--   stored procedure analysis, RAG enrichment, and verification.
--
-- WARNING:
--   This database intentionally contains bad data and broken
--   procedures for testing. Do not use in production.
-- ============================================================

DROP DATABASE IF EXISTS employee_payroll_rca_demo;
CREATE DATABASE employee_payroll_rca_demo
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE employee_payroll_rca_demo;

-- ============================================================
-- 1. MASTER DATA
-- ============================================================

CREATE TABLE departments (
    department_id      INT PRIMARY KEY AUTO_INCREMENT,
    department_code    VARCHAR(20) NOT NULL UNIQUE,
    department_name    VARCHAR(100) NOT NULL,
    active_flag        TINYINT(1) NOT NULL DEFAULT 1,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    employee_id        VARCHAR(20) PRIMARY KEY,
    employee_name      VARCHAR(120) NOT NULL,
    department_id      INT NULL,
    date_of_birth      DATE NULL,
    date_of_birth_raw  VARCHAR(30) NULL,
    hire_date          DATE NULL,
    employment_status  VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    email_address      VARCHAR(150) NULL,
    currency_code      CHAR(3) NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE employee_payroll_profiles (
    employee_id             VARCHAR(20) PRIMARY KEY,
    billing_rate            DECIMAL(12,2) NULL,
    standard_hours          DECIMAL(8,2) NULL,
    overtime_rate_multiplier DECIMAL(6,2) NULL DEFAULT 1.50,
    tax_code                VARCHAR(20) NULL,
    provident_fund_code     VARCHAR(20) NULL,
    payment_mode            VARCHAR(20) NULL,
    effective_from          DATE NOT NULL,
    effective_to            DATE NULL,
    active_flag             TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_profile_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE employee_bank_accounts (
    bank_account_id    BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id        VARCHAR(20) NOT NULL,
    account_number     VARCHAR(40) NULL,
    bank_code          VARCHAR(30) NULL,
    swift_or_ifsc      VARCHAR(30) NULL,
    is_primary         TINYINT(1) NOT NULL DEFAULT 0,
    active_flag        TINYINT(1) NOT NULL DEFAULT 1,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bank_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE tax_configuration (
    tax_code           VARCHAR(20) PRIMARY KEY,
    tax_rate_percent   DECIMAL(7,4) NULL,
    minimum_taxable    DECIMAL(12,2) NOT NULL DEFAULT 0,
    effective_from     DATE NOT NULL,
    effective_to       DATE NULL,
    active_flag        TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE provident_fund_configuration (
    provident_fund_code VARCHAR(20) PRIMARY KEY,
    employee_rate_percent DECIMAL(7,4) NULL,
    employer_rate_percent DECIMAL(7,4) NULL,
    effective_from       DATE NOT NULL,
    effective_to         DATE NULL,
    active_flag          TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE payroll_periods (
    payroll_period_id  INT PRIMARY KEY AUTO_INCREMENT,
    period_code        VARCHAR(20) NOT NULL UNIQUE,
    period_start       DATE NOT NULL,
    period_end         DATE NOT NULL,
    payment_date       DATE NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'OPEN'
);

-- ============================================================
-- 2. TRANSACTION TABLES
-- ============================================================

CREATE TABLE employee_timesheets (
    timesheet_id       BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id        VARCHAR(20) NOT NULL,
    payroll_period_id  INT NOT NULL,
    regular_hours      DECIMAL(8,2) NULL,
    overtime_hours     DECIMAL(8,2) NULL,
    approved_flag      TINYINT(1) NOT NULL DEFAULT 0,
    approved_by        VARCHAR(100) NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_timesheet_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    CONSTRAINT fk_timesheet_period
        FOREIGN KEY (payroll_period_id) REFERENCES payroll_periods(payroll_period_id)
);

CREATE TABLE payroll_runs (
    payroll_run_id     BIGINT PRIMARY KEY AUTO_INCREMENT,
    payroll_period_id  INT NOT NULL,
    run_reference      VARCHAR(50) NOT NULL,
    run_status         VARCHAR(20) NOT NULL,
    started_at         DATETIME NULL,
    completed_at       DATETIME NULL,
    initiated_by       VARCHAR(100) NULL,
    UNIQUE KEY uq_payroll_run_reference (run_reference),
    CONSTRAINT fk_payroll_run_period
        FOREIGN KEY (payroll_period_id) REFERENCES payroll_periods(payroll_period_id)
);

CREATE TABLE payroll_results (
    payroll_result_id  BIGINT PRIMARY KEY AUTO_INCREMENT,
    payroll_run_id     BIGINT NOT NULL,
    payroll_period_id  INT NOT NULL,
    employee_id        VARCHAR(20) NOT NULL,
    age_at_period_end  INT NULL,
    regular_pay        DECIMAL(14,2) NULL,
    overtime_pay       DECIMAL(14,2) NULL,
    gross_pay          DECIMAL(14,2) NULL,
    tax_amount         DECIMAL(14,2) NULL,
    provident_fund_amount DECIMAL(14,2) NULL,
    net_pay            DECIMAL(14,2) NULL,
    calculation_status VARCHAR(30) NOT NULL,
    error_code         VARCHAR(50) NULL,
    error_message      VARCHAR(1000) NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_result_run
        FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(payroll_run_id),
    CONSTRAINT fk_result_period
        FOREIGN KEY (payroll_period_id) REFERENCES payroll_periods(payroll_period_id),
    CONSTRAINT fk_result_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE payment_files (
    payment_file_id    BIGINT PRIMARY KEY AUTO_INCREMENT,
    payroll_run_id     BIGINT NOT NULL,
    file_name          VARCHAR(255) NOT NULL,
    file_path          VARCHAR(500) NULL,
    generation_status  VARCHAR(30) NOT NULL,
    error_message      VARCHAR(1000) NULL,
    generated_at       DATETIME NULL,
    CONSTRAINT fk_payment_file_run
        FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(payroll_run_id)
);

CREATE TABLE payment_file_details (
    payment_file_detail_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_file_id        BIGINT NOT NULL,
    employee_id            VARCHAR(20) NOT NULL,
    account_number         VARCHAR(40) NULL,
    amount                 DECIMAL(14,2) NULL,
    detail_status          VARCHAR(30) NOT NULL,
    error_message          VARCHAR(1000) NULL,
    CONSTRAINT fk_payment_detail_file
        FOREIGN KEY (payment_file_id) REFERENCES payment_files(payment_file_id),
    CONSTRAINT fk_payment_detail_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- ============================================================
-- 3. OPERATIONAL EVIDENCE TABLES
-- ============================================================

CREATE TABLE payroll_job_log (
    job_log_id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    payroll_run_id      BIGINT NULL,
    employee_id         VARCHAR(20) NULL,
    job_name            VARCHAR(120) NOT NULL,
    step_name           VARCHAR(120) NULL,
    execution_status    VARCHAR(30) NOT NULL,
    error_code          VARCHAR(50) NULL,
    error_message       VARCHAR(2000) NULL,
    started_at          DATETIME NOT NULL,
    completed_at        DATETIME NULL,
    CONSTRAINT fk_job_log_run
        FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(payroll_run_id)
);

CREATE TABLE payroll_audit_log (
    audit_id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id          VARCHAR(20) NULL,
    payroll_run_id       BIGINT NULL,
    action_name          VARCHAR(100) NOT NULL,
    object_name          VARCHAR(150) NULL,
    old_value            TEXT NULL,
    new_value            TEXT NULL,
    performed_by         VARCHAR(100) NULL,
    performed_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE application_error_log (
    error_id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_component     VARCHAR(120) NOT NULL,
    employee_id          VARCHAR(20) NULL,
    payroll_run_id       BIGINT NULL,
    exception_type       VARCHAR(200) NULL,
    error_message        VARCHAR(2000) NOT NULL,
    stack_summary        VARCHAR(2000) NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 4. SUPPLEMENTARY KNOWLEDGE / RAG TABLES
--    These must not be treated as affected business objects.
-- ============================================================

CREATE TABLE incident_knowledge_base (
    incident_id          INT PRIMARY KEY AUTO_INCREMENT,
    issue_title          VARCHAR(200) NOT NULL,
    module_name          VARCHAR(100) NOT NULL,
    symptoms             TEXT NULL,
    root_cause           TEXT NULL,
    fix_summary          TEXT NULL,
    proof_of_fix         TEXT NULL,
    approved_flag        TINYINT(1) NOT NULL DEFAULT 0,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_quality_rules (
    rule_id              INT PRIMARY KEY AUTO_INCREMENT,
    rule_name            VARCHAR(150) NOT NULL,
    target_table         VARCHAR(150) NOT NULL,
    target_column        VARCHAR(150) NULL,
    rule_sql             TEXT NOT NULL,
    severity             VARCHAR(20) NOT NULL,
    active_flag          TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE investigation_scenarios (
    scenario_id          INT PRIMARY KEY AUTO_INCREMENT,
    employee_id          VARCHAR(20) NULL,
    scenario_code        VARCHAR(30) NOT NULL UNIQUE,
    scenario_title       VARCHAR(250) NOT NULL,
    expected_root_cause  TEXT NOT NULL,
    expected_objects     VARCHAR(1000) NOT NULL,
    recommended_question TEXT NOT NULL
);

-- ============================================================
-- 5. INDEXES FOR REALISTIC DISCOVERY
-- ============================================================

CREATE INDEX ix_employee_name ON employees(employee_name);
CREATE INDEX ix_employee_dob ON employees(date_of_birth);
CREATE INDEX ix_timesheet_employee_period
    ON employee_timesheets(employee_id, payroll_period_id);
CREATE INDEX ix_result_employee_period
    ON payroll_results(employee_id, payroll_period_id);
CREATE INDEX ix_job_employee_run
    ON payroll_job_log(employee_id, payroll_run_id);
CREATE INDEX ix_error_employee_run
    ON application_error_log(employee_id, payroll_run_id);

-- ============================================================
-- 6. VIEWS
-- ============================================================

CREATE OR REPLACE VIEW vw_employee_payroll_context AS
SELECT
    e.employee_id,
    e.employee_name,
    e.date_of_birth,
    e.date_of_birth_raw,
    e.employment_status,
    e.currency_code,
    p.billing_rate,
    p.standard_hours,
    p.tax_code,
    p.provident_fund_code,
    p.payment_mode,
    b.account_number,
    b.bank_code,
    b.swift_or_ifsc
FROM employees e
LEFT JOIN employee_payroll_profiles p
    ON p.employee_id = e.employee_id
   AND p.active_flag = 1
LEFT JOIN employee_bank_accounts b
    ON b.employee_id = e.employee_id
   AND b.is_primary = 1
   AND b.active_flag = 1;

CREATE OR REPLACE VIEW vw_payroll_failure_summary AS
SELECT
    r.payroll_result_id,
    r.employee_id,
    r.payroll_run_id,
    r.calculation_status,
    r.error_code,
    r.error_message,
    j.job_name,
    j.step_name,
    j.execution_status,
    j.started_at
FROM payroll_results r
LEFT JOIN payroll_job_log j
    ON j.payroll_run_id = r.payroll_run_id
   AND j.employee_id = r.employee_id
WHERE r.calculation_status <> 'SUCCESS';

-- ============================================================
-- 7. SAMPLE DATA
-- ============================================================

INSERT INTO departments (department_code, department_name)
VALUES
('IT', 'Information Technology'),
('FIN', 'Finance'),
('OPS', 'Operations'),
('HR', 'Human Resources');

INSERT INTO tax_configuration
(tax_code, tax_rate_percent, minimum_taxable, effective_from, active_flag)
VALUES
('TAX10', 10.0000, 0, '2026-01-01', 1),
('TAX20', 20.0000, 50000, '2026-01-01', 1),
('TAXNULL', NULL, 0, '2026-01-01', 1);

INSERT INTO provident_fund_configuration
(provident_fund_code, employee_rate_percent, employer_rate_percent, effective_from, active_flag)
VALUES
('PF12', 12.0000, 12.0000, '2026-01-01', 1),
('PFNULL', NULL, NULL, '2026-01-01', 1);

INSERT INTO payroll_periods
(period_code, period_start, period_end, payment_date, status)
VALUES
('2026-06', '2026-06-01', '2026-06-30', '2026-07-05', 'CLOSED'),
('2026-07', '2026-07-01', '2026-07-31', '2026-08-05', 'OPEN');

INSERT INTO employees
(employee_id, employee_name, department_id, date_of_birth, date_of_birth_raw,
 hire_date, employment_status, email_address, currency_code)
VALUES
('E000', 'Healthy Baseline Employee', 1, '1990-01-15', '1990-01-15', '2020-01-01', 'ACTIVE', 'e000@example.com', 'USD'),
('E001', 'Null DOB Employee',         1, NULL,         NULL,         '2020-02-01', 'ACTIVE', 'e001@example.com', 'USD'),
('E002', 'Invalid DOB Text Employee', 2, NULL,         '31-31-1990', '2021-03-01', 'ACTIVE', 'e002@example.com', 'USD'),
('E003', 'Null Billing Rate Employee',2, '1988-05-12', '1988-05-12', '2022-04-01', 'ACTIVE', 'e003@example.com', 'USD'),
('E004', 'Zero Billing Rate Employee',2, '1985-08-20', '1985-08-20', '2022-05-01', 'ACTIVE', 'e004@example.com', 'USD'),
('E005', 'Missing Tax Config Employee',3,'1992-10-01','1992-10-01','2023-01-15','ACTIVE','e005@example.com','USD'),
('E006', 'Null Bank Account Employee',3,'1987-02-14','1987-02-14','2021-07-01','ACTIVE','e006@example.com','USD'),
('E007', 'Invalid Bank Code Employee',3,'1989-09-09','1989-09-09','2020-06-01','ACTIVE','e007@example.com','USD'),
('E008', 'Duplicate Payroll Employee',4,'1991-11-11','1991-11-11','2019-12-01','ACTIVE','e008@example.com','USD'),
('E009', 'Unapproved Timesheet Employee',1,'1993-03-03','1993-03-03','2024-01-01','ACTIVE','e009@example.com','USD'),
('E010', 'Missing Timesheet Employee',1,'1994-04-04','1994-04-04','2024-02-01','ACTIVE','e010@example.com','USD'),
('E011', 'Negative Overtime Employee',2,'1986-06-06','1986-06-06','2020-09-01','ACTIVE','e011@example.com','USD'),
('E012', 'Inactive Employee Paid',2,'1982-12-12','1982-12-12','2018-01-01','INACTIVE','e012@example.com','USD'),
('E013', 'Missing Currency Employee',3,'1990-07-07','1990-07-07','2021-11-01','ACTIVE','e013@example.com',NULL),
('E014', 'Null PF Rate Employee',3,'1984-01-25','1984-01-25','2017-08-01','ACTIVE','e014@example.com','USD'),
('E015', 'Duplicate Primary Bank Employee',4,'1995-05-05','1995-05-05','2025-01-01','ACTIVE','e015@example.com','USD'),
('E020', 'Duplicate Payroll Retry Employee',4,'1992-02-20','1992-02-20','2022-02-02','ACTIVE','e020@example.com','USD');

INSERT INTO employee_payroll_profiles
(employee_id, billing_rate, standard_hours, overtime_rate_multiplier,
 tax_code, provident_fund_code, payment_mode, effective_from, active_flag)
VALUES
('E000', 50.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E001', 55.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E002', 60.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E003', NULL, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E004', 0.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E005', 65.00, 160.00, 1.50, 'TAX404', 'PF12', 'BANK', '2026-01-01', 1),
('E006', 52.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E007', 58.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E008', 70.00, 160.00, 1.50, 'TAX20', 'PF12', 'BANK', '2026-01-01', 1),
('E009', 48.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E010', 45.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E011', 62.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E012', 75.00, 160.00, 1.50, 'TAX20', 'PF12', 'BANK', '2026-01-01', 1),
('E013', 50.00, 160.00, 1.50, 'TAX10', 'PF12', 'BANK', '2026-01-01', 1),
('E014', 56.00, 160.00, 1.50, 'TAX10', 'PFNULL', 'BANK', '2026-01-01', 1),
('E015', 68.00, 160.00, 1.50, 'TAX20', 'PF12', 'BANK', '2026-01-01', 1),
('E020', 80.00, 160.00, 1.50, 'TAX20', 'PF12', 'BANK', '2026-01-01', 1);

INSERT INTO employee_bank_accounts
(employee_id, account_number, bank_code, swift_or_ifsc, is_primary, active_flag)
VALUES
('E000','1000000001','BANK01','VALID001',1,1),
('E001','1000000002','BANK01','VALID002',1,1),
('E002','1000000003','BANK01','VALID003',1,1),
('E003','1000000004','BANK01','VALID004',1,1),
('E004','1000000005','BANK01','VALID005',1,1),
('E005','1000000006','BANK01','VALID006',1,1),
('E006',NULL,'BANK01','VALID007',1,1),
('E007','1000000008','@@BAD@@','INVALID',1,1),
('E008','1000000009','BANK01','VALID009',1,1),
('E009','1000000010','BANK01','VALID010',1,1),
('E010','1000000011','BANK01','VALID011',1,1),
('E011','1000000012','BANK01','VALID012',1,1),
('E012','1000000013','BANK01','VALID013',1,1),
('E013','1000000014','BANK01','VALID014',1,1),
('E014','1000000015','BANK01','VALID015',1,1),
('E015','1000000016','BANK01','VALID016',1,1),
('E015','1000000099','BANK02','VALID099',1,1),
('E020','1000000020','BANK01','VALID020',1,1);

INSERT INTO employee_timesheets
(employee_id, payroll_period_id, regular_hours, overtime_hours, approved_flag, approved_by)
VALUES
('E000', 2, 160, 8, 1, 'manager1'),
('E001', 2, 160, 0, 1, 'manager1'),
('E002', 2, 160, 0, 1, 'manager1'),
('E003', 2, 160, 5, 1, 'manager2'),
('E004', 2, 160, 0, 1, 'manager2'),
('E005', 2, 160, 2, 1, 'manager3'),
('E006', 2, 160, 0, 1, 'manager3'),
('E007', 2, 160, 0, 1, 'manager3'),
('E008', 2, 160, 10, 1, 'manager4'),
('E009', 2, 160, 0, 0, NULL),
('E011', 2, 160, -5, 1, 'manager2'),
('E012', 2, 160, 0, 1, 'manager2'),
('E013', 2, 160, 0, 1, 'manager3'),
('E014', 2, 160, 0, 1, 'manager3'),
('E015', 2, 160, 0, 1, 'manager4'),
('E020', 2, 160, 6, 1, 'manager4');

INSERT INTO payroll_runs
(payroll_period_id, run_reference, run_status, started_at, completed_at, initiated_by)
VALUES
(2, 'RUN-2026-07-001', 'FAILED',  '2026-07-12 18:00:00', '2026-07-12 18:15:00', 'scheduler'),
(2, 'RUN-2026-07-RETRY', 'COMPLETED', '2026-07-12 19:00:00', '2026-07-12 19:20:00', 'scheduler');

-- Intentional duplicate payroll results for E008 and E020.
INSERT INTO payroll_results
(payroll_run_id, payroll_period_id, employee_id, age_at_period_end,
 regular_pay, overtime_pay, gross_pay, tax_amount,
 provident_fund_amount, net_pay, calculation_status, error_code, error_message)
VALUES
(1,2,'E000',36,8000,600,8600,860,1032,6708,'SUCCESS',NULL,NULL),
(1,2,'E001',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','DOB_NULL','Age calculation failed because date_of_birth is NULL'),
(1,2,'E002',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','DOB_INVALID','Raw date of birth cannot be converted to DATE'),
(1,2,'E003',38,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','RATE_NULL','Billing rate is NULL'),
(1,2,'E004',40,0,0,0,0,0,0,'FAILED','RATE_ZERO','Billing rate is zero'),
(1,2,'E005',33,10400,195,10595,NULL,1271.40,NULL,'FAILED','TAX_CONFIG_MISSING','Tax code TAX404 is not configured'),
(1,2,'E006',39,8320,0,8320,832,998.40,6489.60,'SUCCESS',NULL,NULL),
(1,2,'E007',36,9280,0,9280,928,1113.60,7238.40,'SUCCESS',NULL,NULL),
(1,2,'E008',34,11200,1050,12250,2450,1470,8330,'SUCCESS',NULL,NULL),
(1,2,'E008',34,11200,1050,12250,2450,1470,8330,'SUCCESS',NULL,'Duplicate result inserted by retry logic'),
(1,2,'E009',33,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','TIMESHEET_NOT_APPROVED','Timesheet is not approved'),
(1,2,'E010',32,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','TIMESHEET_MISSING','No timesheet found'),
(1,2,'E011',40,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','NEGATIVE_OVERTIME','Overtime hours cannot be negative'),
(1,2,'E012',43,12000,0,12000,2400,1440,8160,'SUCCESS',NULL,'Inactive employee was incorrectly included'),
(1,2,'E013',36,NULL,NULL,NULL,NULL,NULL,NULL,'FAILED','CURRENCY_NULL','Employee currency is NULL'),
(1,2,'E014',42,8960,0,8960,896,NULL,NULL,'FAILED','PF_RATE_NULL','Provident fund rate is NULL'),
(1,2,'E015',31,10880,0,10880,2176,1305.60,7398.40,'SUCCESS',NULL,NULL),
(1,2,'E020',34,12800,720,13520,2704,1622.40,9193.60,'SUCCESS',NULL,NULL),
(2,2,'E020',34,12800,720,13520,2704,1622.40,9193.60,'SUCCESS',NULL,'Duplicate payroll created by retry run');

INSERT INTO payroll_job_log
(payroll_run_id, employee_id, job_name, step_name, execution_status,
 error_code, error_message, started_at, completed_at)
VALUES
(1,'E001','Monthly Payroll','Calculate Employee Payroll','FAILED','DOB_NULL',
 'sp_calculate_employee_payroll attempted age calculation with NULL DOB',
 '2026-07-12 18:01:00','2026-07-12 18:01:02'),
(1,'E002','Monthly Payroll','Validate Employee Data','FAILED','DOB_INVALID',
 'date_of_birth_raw contains invalid date text',
 '2026-07-12 18:01:03','2026-07-12 18:01:04'),
(1,'E003','Monthly Payroll','Calculate Gross Pay','FAILED','RATE_NULL',
 'Billing rate is NULL',
 '2026-07-12 18:02:00','2026-07-12 18:02:01'),
(1,'E005','Monthly Payroll','Calculate Tax','FAILED','TAX_CONFIG_MISSING',
 'No active tax configuration found for TAX404',
 '2026-07-12 18:03:00','2026-07-12 18:03:01'),
(1,'E009','Monthly Payroll','Load Timesheet','FAILED','TIMESHEET_NOT_APPROVED',
 'Timesheet exists but is not approved',
 '2026-07-12 18:04:00','2026-07-12 18:04:01'),
(1,'E010','Monthly Payroll','Load Timesheet','FAILED','TIMESHEET_MISSING',
 'No timesheet found for the payroll period',
 '2026-07-12 18:05:00','2026-07-12 18:05:01'),
(1,'E020','Monthly Payroll','Persist Payroll Result','SUCCESS',NULL,
 'Initial payroll result created',
 '2026-07-12 18:10:00','2026-07-12 18:10:01'),
(2,'E020','Monthly Payroll Retry','Persist Payroll Result','SUCCESS',NULL,
 'Retry created a second payroll result because no idempotency check exists',
 '2026-07-12 19:10:00','2026-07-12 19:10:01');

INSERT INTO application_error_log
(source_component, employee_id, payroll_run_id, exception_type,
 error_message, stack_summary, created_at)
VALUES
('PayrollService','E001',1,'PayrollValidationException',
 'DOB is required for age calculation',
 'sp_calculate_employee_payroll -> TIMESTAMPDIFF(YEAR, NULL, period_end)',
 '2026-07-12 18:01:02'),
('PayrollService','E003',1,'PayrollCalculationException',
 'Cannot calculate regular pay because billing_rate is NULL',
 'sp_calculate_employee_payroll -> regular_hours * billing_rate',
 '2026-07-12 18:02:01'),
('PayrollService','E020',2,'DuplicateProcessingWarning',
 'Employee payroll was processed again during retry',
 'sp_process_payroll_retry -> missing existence check',
 '2026-07-12 19:10:01');

INSERT INTO payroll_audit_log
(employee_id, payroll_run_id, action_name, object_name, old_value, new_value, performed_by, performed_at)
VALUES
('E020',1,'INSERT','payroll_results',NULL,'Initial payroll row created','scheduler','2026-07-12 18:10:01'),
('E020',2,'INSERT','payroll_results',NULL,'Duplicate payroll row created during retry','scheduler','2026-07-12 19:10:01');

-- ============================================================
-- 8. INTENTIONALLY BROKEN STORED PROCEDURES
-- ============================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_calculate_employee_age $$
CREATE PROCEDURE sp_calculate_employee_age(
    IN p_employee_id VARCHAR(20),
    IN p_period_end DATE
)
BEGIN
    DECLARE v_dob DATE;
    DECLARE v_age INT;

    SELECT date_of_birth
      INTO v_dob
      FROM employees
     WHERE employee_id = p_employee_id;

    -- INTENTIONAL DEFECT:
    -- No explicit NULL check before age calculation.
    SET v_age = TIMESTAMPDIFF(YEAR, v_dob, p_period_end);

    SELECT p_employee_id AS employee_id,
           v_dob AS date_of_birth,
           v_age AS calculated_age;
END $$

DROP PROCEDURE IF EXISTS sp_calculate_employee_payroll $$
CREATE PROCEDURE sp_calculate_employee_payroll(
    IN p_employee_id VARCHAR(20),
    IN p_payroll_period_id INT,
    IN p_payroll_run_id BIGINT
)
BEGIN
    DECLARE v_period_end DATE;
    DECLARE v_dob DATE;
    DECLARE v_rate DECIMAL(12,2);
    DECLARE v_regular_hours DECIMAL(8,2);
    DECLARE v_overtime_hours DECIMAL(8,2);
    DECLARE v_multiplier DECIMAL(6,2);
    DECLARE v_tax_rate DECIMAL(7,4);
    DECLARE v_pf_rate DECIMAL(7,4);
    DECLARE v_age INT;
    DECLARE v_regular_pay DECIMAL(14,2);
    DECLARE v_overtime_pay DECIMAL(14,2);
    DECLARE v_gross_pay DECIMAL(14,2);
    DECLARE v_tax DECIMAL(14,2);
    DECLARE v_pf DECIMAL(14,2);
    DECLARE v_net DECIMAL(14,2);

    SELECT period_end
      INTO v_period_end
      FROM payroll_periods
     WHERE payroll_period_id = p_payroll_period_id;

    SELECT e.date_of_birth,
           p.billing_rate,
           p.overtime_rate_multiplier,
           t.regular_hours,
           t.overtime_hours,
           tc.tax_rate_percent,
           pfc.employee_rate_percent
      INTO v_dob,
           v_rate,
           v_multiplier,
           v_regular_hours,
           v_overtime_hours,
           v_tax_rate,
           v_pf_rate
      FROM employees e
      JOIN employee_payroll_profiles p
        ON p.employee_id = e.employee_id
       AND p.active_flag = 1
      LEFT JOIN employee_timesheets t
        ON t.employee_id = e.employee_id
       AND t.payroll_period_id = p_payroll_period_id
      LEFT JOIN tax_configuration tc
        ON tc.tax_code = p.tax_code
       AND tc.active_flag = 1
      LEFT JOIN provident_fund_configuration pfc
        ON pfc.provident_fund_code = p.provident_fund_code
       AND pfc.active_flag = 1
     WHERE e.employee_id = p_employee_id;

    -- INTENTIONAL DEFECTS:
    -- 1. No NULL check for date_of_birth.
    -- 2. No NULL or zero validation for billing_rate.
    -- 3. No approval check for timesheet.
    -- 4. No negative overtime validation.
    -- 5. Missing tax/PF configuration is not handled.
    SET v_age = TIMESTAMPDIFF(YEAR, v_dob, v_period_end);
    SET v_regular_pay = v_regular_hours * v_rate;
    SET v_overtime_pay = v_overtime_hours * v_rate * v_multiplier;
    SET v_gross_pay = v_regular_pay + v_overtime_pay;
    SET v_tax = v_gross_pay * (v_tax_rate / 100);
    SET v_pf = v_gross_pay * (v_pf_rate / 100);
    SET v_net = v_gross_pay - v_tax - v_pf;

    INSERT INTO payroll_results
    (payroll_run_id, payroll_period_id, employee_id, age_at_period_end,
     regular_pay, overtime_pay, gross_pay, tax_amount,
     provident_fund_amount, net_pay, calculation_status)
    VALUES
    (p_payroll_run_id, p_payroll_period_id, p_employee_id, v_age,
     v_regular_pay, v_overtime_pay, v_gross_pay, v_tax,
     v_pf, v_net, 'SUCCESS');
END $$

DROP PROCEDURE IF EXISTS sp_process_payroll_retry $$
CREATE PROCEDURE sp_process_payroll_retry(
    IN p_employee_id VARCHAR(20),
    IN p_payroll_period_id INT,
    IN p_payroll_run_id BIGINT
)
BEGIN
    -- INTENTIONAL DEFECT:
    -- No idempotency or duplicate-existence check before reprocessing.
    CALL sp_calculate_employee_payroll(
        p_employee_id,
        p_payroll_period_id,
        p_payroll_run_id
    );
END $$

DROP PROCEDURE IF EXISTS sp_generate_payment_file $$
CREATE PROCEDURE sp_generate_payment_file(
    IN p_payroll_run_id BIGINT
)
BEGIN
    DECLARE v_file_id BIGINT;

    INSERT INTO payment_files
    (payroll_run_id, file_name, file_path, generation_status, generated_at)
    VALUES
    (p_payroll_run_id,
     CONCAT('payroll_', p_payroll_run_id, '.csv'),
     '/payroll/output',
     'STARTED',
     NOW());

    SET v_file_id = LAST_INSERT_ID();

    -- INTENTIONAL DEFECT:
    -- Does not reject NULL account numbers or duplicate primary accounts.
    INSERT INTO payment_file_details
    (payment_file_id, employee_id, account_number, amount,
     detail_status, error_message)
    SELECT
        v_file_id,
        r.employee_id,
        b.account_number,
        r.net_pay,
        CASE
            WHEN b.account_number IS NULL THEN 'FAILED'
            ELSE 'READY'
        END,
        CASE
            WHEN b.account_number IS NULL
                THEN 'Primary bank account number is NULL'
            ELSE NULL
        END
    FROM payroll_results r
    LEFT JOIN employee_bank_accounts b
      ON b.employee_id = r.employee_id
     AND b.is_primary = 1
     AND b.active_flag = 1
    WHERE r.payroll_run_id = p_payroll_run_id
      AND r.calculation_status = 'SUCCESS';

    UPDATE payment_files
       SET generation_status = 'COMPLETED'
     WHERE payment_file_id = v_file_id;
END $$

DELIMITER ;

-- ============================================================
-- 9. DATA QUALITY RULES
-- ============================================================

INSERT INTO data_quality_rules
(rule_name, target_table, target_column, rule_sql, severity)
VALUES
('Employee DOB must not be NULL',
 'employees',
 'date_of_birth',
 'SELECT employee_id FROM employees WHERE date_of_birth IS NULL',
 'HIGH'),

('Raw DOB must be parseable',
 'employees',
 'date_of_birth_raw',
 'SELECT employee_id, date_of_birth_raw FROM employees WHERE date_of_birth IS NULL AND date_of_birth_raw IS NOT NULL',
 'HIGH'),

('Billing rate must be positive',
 'employee_payroll_profiles',
 'billing_rate',
 'SELECT employee_id, billing_rate FROM employee_payroll_profiles WHERE billing_rate IS NULL OR billing_rate <= 0',
 'HIGH'),

('Timesheet must be approved',
 'employee_timesheets',
 'approved_flag',
 'SELECT employee_id, payroll_period_id FROM employee_timesheets WHERE approved_flag = 0',
 'HIGH'),

('Overtime must not be negative',
 'employee_timesheets',
 'overtime_hours',
 'SELECT employee_id, payroll_period_id, overtime_hours FROM employee_timesheets WHERE overtime_hours < 0',
 'HIGH'),

('Primary account number is required',
 'employee_bank_accounts',
 'account_number',
 'SELECT employee_id FROM employee_bank_accounts WHERE is_primary = 1 AND active_flag = 1 AND account_number IS NULL',
 'HIGH'),

('Only one active primary bank account is allowed',
 'employee_bank_accounts',
 'is_primary',
 'SELECT employee_id, COUNT(*) FROM employee_bank_accounts WHERE is_primary = 1 AND active_flag = 1 GROUP BY employee_id HAVING COUNT(*) > 1',
 'HIGH'),

('Payroll result must be unique by period and employee',
 'payroll_results',
 'employee_id',
 'SELECT payroll_period_id, employee_id, COUNT(*) FROM payroll_results GROUP BY payroll_period_id, employee_id HAVING COUNT(*) > 1',
 'CRITICAL');

-- ============================================================
-- 10. APPROVED KNOWLEDGE FOR RAG ENRICHMENT
-- ============================================================

INSERT INTO incident_knowledge_base
(issue_title, module_name, symptoms, root_cause, fix_summary, proof_of_fix, approved_flag)
VALUES
(
 'Payroll age calculation fails for employees with missing DOB',
 'Payroll',
 'Payroll calculation fails or returns NULL age when employee date_of_birth is NULL.',
 'Stored procedure calculates age without validating date_of_birth.',
 'Validate DOB before TIMESTAMPDIFF. Route invalid records to a data-quality queue and correct source data through an approved process.',
 'Re-run read-only DOB validation, execute the corrected procedure in test, and confirm one successful payroll result.',
 1
),
(
 'Duplicate payroll result created during retry',
 'Payroll',
 'The same employee has more than one payroll result for the same payroll period.',
 'Retry procedure reprocesses payroll without checking whether a result already exists.',
 'Add an idempotency key or unique constraint and return the existing result during retry.',
 'Verify one result per employee and payroll period after retry.',
 1
),
(
 'Payment file fails because bank account is missing',
 'Payments',
 'Payment detail cannot be generated for an employee.',
 'Primary bank account number is NULL.',
 'Correct the approved bank account record and add validation before payment-file generation.',
 'Verify that every payment detail has a non-NULL account number.',
 1
);

-- ============================================================
-- 11. TEST SCENARIO CATALOG
-- ============================================================

INSERT INTO investigation_scenarios
(employee_id, scenario_code, scenario_title, expected_root_cause,
 expected_objects, recommended_question)
VALUES
(
 'E001',
 'SCN-001',
 'NULL DOB causes age calculation failure',
 'employees.date_of_birth is NULL and sp_calculate_employee_age / sp_calculate_employee_payroll calculate age without an explicit NULL validation.',
 'employees, payroll_results, payroll_job_log, application_error_log, sp_calculate_employee_age, sp_calculate_employee_payroll',
 'Investigate payroll failure for employee E001. Find the employee record, DOB value, relevant payroll procedures, error logs, evidence SQL, root cause, safe fix, and verification SQL. Use live database evidence first.'
),
(
 'E002',
 'SCN-002',
 'Invalid DOB text cannot be converted',
 'employees.date_of_birth_raw contains invalid date text while date_of_birth is NULL.',
 'employees, payroll_results, payroll_job_log',
 'Investigate why employee E002 has a DOB validation failure. Find the invalid stored value and the affected payroll objects.'
),
(
 'E003',
 'SCN-003',
 'NULL billing rate prevents salary calculation',
 'employee_payroll_profiles.billing_rate is NULL and the payroll procedure multiplies hours by the rate without validation.',
 'employee_payroll_profiles, employee_timesheets, payroll_results, sp_calculate_employee_payroll',
 'Investigate salary calculation failure for employee E003 using database evidence.'
),
(
 'E005',
 'SCN-005',
 'Missing tax configuration',
 'Employee profile references TAX404, which does not exist in active tax_configuration.',
 'employee_payroll_profiles, tax_configuration, payroll_results, payroll_job_log',
 'Investigate tax calculation failure for employee E005.'
),
(
 'E006',
 'SCN-006',
 'NULL primary bank account',
 'The active primary bank account row exists but account_number is NULL.',
 'employee_bank_accounts, payment_file_details, sp_generate_payment_file',
 'Investigate payment-file failure risk for employee E006.'
),
(
 'E008',
 'SCN-008',
 'Duplicate payroll result',
 'Two payroll_results rows exist for the same employee and payroll period.',
 'payroll_results, payroll_runs, payroll_audit_log',
 'Investigate duplicate payroll generation for employee E008.'
),
(
 'E009',
 'SCN-009',
 'Timesheet is not approved',
 'employee_timesheets.approved_flag is 0, but the payroll procedure does not enforce approval.',
 'employee_timesheets, payroll_results, payroll_job_log, sp_calculate_employee_payroll',
 'Investigate payroll failure for employee E009.'
),
(
 'E010',
 'SCN-010',
 'Timesheet is missing',
 'No employee_timesheets row exists for E010 in payroll period 2026-07.',
 'employees, employee_timesheets, payroll_results, payroll_job_log',
 'Investigate why payroll cannot be calculated for employee E010.'
),
(
 'E011',
 'SCN-011',
 'Negative overtime hours',
 'employee_timesheets.overtime_hours is negative and the payroll procedure does not validate it.',
 'employee_timesheets, payroll_results, sp_calculate_employee_payroll',
 'Investigate invalid overtime data for employee E011.'
),
(
 'E020',
 'SCN-020',
 'Retry creates duplicate payroll',
 'sp_process_payroll_retry has no idempotency check and a second run creates another payroll result.',
 'payroll_results, payroll_runs, payroll_job_log, payroll_audit_log, sp_process_payroll_retry',
 'Investigate why employee E020 was paid twice after a retry.'
);

-- ============================================================
-- 12. OPTIONAL HARDENING TEST
--     Keep this commented out initially because it would prevent
--     intentional duplicate rows.
-- ============================================================

-- ALTER TABLE payroll_results
-- ADD CONSTRAINT uq_payroll_result_employee_period
-- UNIQUE (payroll_period_id, employee_id);

-- ============================================================
-- 13. QUICK VALIDATION QUERIES
-- ============================================================

-- Check that all important objects exist:
-- SHOW FULL TABLES;
-- SHOW PROCEDURE STATUS WHERE Db = 'employee_payroll_rca_demo';

-- Baseline healthy employee:
-- SELECT * FROM vw_employee_payroll_context WHERE employee_id = 'E000';

-- E001 root-cause evidence:
-- SELECT employee_id, date_of_birth, date_of_birth_raw
-- FROM employees
-- WHERE employee_id = 'E001';
--
-- SELECT *
-- FROM payroll_results
-- WHERE employee_id = 'E001';
--
-- SELECT *
-- FROM payroll_job_log
-- WHERE employee_id = 'E001';
--
-- SELECT *
-- FROM application_error_log
-- WHERE employee_id = 'E001';
--
-- SHOW CREATE PROCEDURE sp_calculate_employee_age;
-- SHOW CREATE PROCEDURE sp_calculate_employee_payroll;

-- Duplicate payroll evidence:
-- SELECT payroll_period_id, employee_id, COUNT(*) AS result_count
-- FROM payroll_results
-- GROUP BY payroll_period_id, employee_id
-- HAVING COUNT(*) > 1;

-- Verify that knowledge tables are supplementary only:
-- SELECT * FROM incident_knowledge_base WHERE module_name = 'Payroll';

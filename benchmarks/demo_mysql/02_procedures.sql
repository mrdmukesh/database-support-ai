DROP PROCEDURE IF EXISTS sp_retry_failed_lab_orders;
DROP PROCEDURE IF EXISTS sp_generate_claims;
DROP PROCEDURE IF EXISTS sp_process_checked_out_appointments;
DROP PROCEDURE IF EXISTS sp_reconcile_claims;

DELIMITER //

CREATE PROCEDURE sp_retry_failed_lab_orders()
BEGIN
    INSERT INTO lab_orders (
        appointment_id,
        patient_id,
        lab_order_number,
        lab_status,
        ordered_at,
        retry_source,
        created_at
    )
    SELECT
        a.appointment_id,
        a.patient_id,
        CONCAT('LAB-', SUBSTRING_INDEX(a.appointment_number, '-', -1), '-RETRY'),
        'ORDERED',
        NOW(),
        'RETRY_JOB',
        NOW()
    FROM appointments a
    WHERE a.appointment_status = 'CHECKED_OUT';
END//

CREATE PROCEDURE sp_generate_claims()
BEGIN
    INSERT INTO claims (appointment_id, claim_number, claim_status, created_at)
    SELECT
        a.appointment_id,
        CONCAT('CLM-', SUBSTRING_INDEX(a.appointment_number, '-', -1)),
        'CREATED',
        NOW()
    FROM appointments a
    WHERE a.appointment_status = 'CHECKED_OUT'
      AND NOT EXISTS (
          SELECT 1
          FROM lab_orders l
          WHERE l.appointment_id = a.appointment_id
            AND l.lab_status IN ('ORDERED', 'PENDING', 'RETRY')
      )
      AND NOT EXISTS (
          SELECT 1
          FROM claims c
          WHERE c.appointment_id = a.appointment_id
      );
END//

CREATE PROCEDURE sp_process_checked_out_appointments()
BEGIN
    SELECT appointment_id, appointment_number
    FROM appointments
    WHERE appointment_status = 'CHECKED_OUT'
      AND DATE(checked_out_at) = CURDATE()
    ORDER BY checked_out_at;
END//

CREATE PROCEDURE sp_reconcile_claims()
BEGIN
    START TRANSACTION;
    UPDATE claims
    SET claim_status = 'RECONCILED'
    WHERE claim_status = 'CREATED';

    UPDATE appointments
    SET appointment_status = 'RECONCILED'
    WHERE appointment_id IN (
        SELECT appointment_id
        FROM claims
        WHERE claim_status = 'RECONCILED'
    );
    COMMIT;
END//

DELIMITER ;

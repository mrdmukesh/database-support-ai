IF EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-003') THROW 51002, 'Scenario contaminated before injection', 1; SELECT 'precondition_valid' ValidationStatus;
GO

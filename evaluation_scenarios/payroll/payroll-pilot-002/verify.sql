IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-PAYROLL-002' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[pay_periods] WHERE Details='EVAL-PAYROLL-002')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'RUN-2026-07-A' ExpectedEntity, 'EVAL-PAYROLL-002' EvidenceValue;
GO

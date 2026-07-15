IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-003' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[diagnoses] WHERE Details='EVAL-CLINIC-003')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'LAB-4403' ExpectedEntity, 'EVAL-CLINIC-003' EvidenceValue;
GO

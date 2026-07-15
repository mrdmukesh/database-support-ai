IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-001' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[appointments] WHERE Details='EVAL-CLINIC-001')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'APT-2101' ExpectedEntity, 'EVAL-CLINIC-001' EvidenceValue;
GO

IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-CLINIC-004' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[procedures_performed] WHERE Details='EVAL-CLINIC-004')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'ENC-5504' ExpectedEntity, 'EVAL-CLINIC-004' EvidenceValue;
GO

IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-001' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[transactions] WHERE Details='EVAL-BANKING-001')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'TRF-3101' ExpectedEntity, 'EVAL-BANKING-001' EvidenceValue;
GO

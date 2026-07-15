IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-004' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[payment_instructions] WHERE Details='EVAL-BANKING-004')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'BAT-3104' ExpectedEntity, 'EVAL-BANKING-004' EvidenceValue;
GO

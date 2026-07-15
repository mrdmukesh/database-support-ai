IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-BANKING-002' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[transfers] WHERE Details='EVAL-BANKING-002')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'PMT-3102' ExpectedEntity, 'EVAL-BANKING-002' EvidenceValue;
GO

IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-005' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[allocations] WHERE Details='EVAL-ORDERS-005')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'PO-1205' ExpectedEntity, 'EVAL-ORDERS-005' EvidenceValue;
GO

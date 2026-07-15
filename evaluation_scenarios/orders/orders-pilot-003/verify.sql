IF NOT (EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='EVAL-ORDERS-003' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[sales_orders] WHERE Details='EVAL-ORDERS-003')) THROW 51001, 'Scenario defect not reproducible', 1; SELECT 'SKU-8103' ExpectedEntity, 'EVAL-ORDERS-003' EvidenceValue;
GO

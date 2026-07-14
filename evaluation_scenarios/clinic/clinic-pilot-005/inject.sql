INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-CLINIC-005','Open','Synthetic pilot defect for PAT-6605','EVAL-CLINIC-005'); UPDATE eval.[prescriptions] SET Status='Exception',Details='EVAL-CLINIC-005' WHERE [PrescriptionsId]=1;
GO

INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-CLINIC-003','Open','Synthetic pilot defect for LAB-4403','EVAL-CLINIC-003'); UPDATE eval.[diagnoses] SET Status='Exception',Details='EVAL-CLINIC-003' WHERE [DiagnosesId]=1;
GO

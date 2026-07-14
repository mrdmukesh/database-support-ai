INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-CLINIC-002','Open','Synthetic pilot defect for CLM-3302','EVAL-CLINIC-002'); UPDATE eval.[encounters] SET Status='Exception',Details='EVAL-CLINIC-002' WHERE [EncountersId]=1;
GO

INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-BANKING-003','Open','Synthetic pilot defect for ACC-3103','EVAL-BANKING-003'); UPDATE eval.[beneficiaries] SET Status='Exception',Details='EVAL-BANKING-003' WHERE [BeneficiariesId]=1;
GO

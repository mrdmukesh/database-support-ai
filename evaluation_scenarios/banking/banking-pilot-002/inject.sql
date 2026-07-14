INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-BANKING-002','Open','Synthetic pilot defect for PMT-3102','EVAL-BANKING-002'); UPDATE eval.[transfers] SET Status='Exception',Details='EVAL-BANKING-002' WHERE [TransfersId]=1;
GO

INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-BANKING-005','Open','Synthetic pilot defect for TXN-3105','EVAL-BANKING-005'); UPDATE eval.[loans] SET Status='Exception',Details='EVAL-BANKING-005' WHERE [LoansId]=1;
GO

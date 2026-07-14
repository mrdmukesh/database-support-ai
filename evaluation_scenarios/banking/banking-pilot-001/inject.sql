INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-BANKING-001','Open','Synthetic pilot defect for TRF-3101','EVAL-BANKING-001'); UPDATE eval.[transactions] SET Status='Exception',Details='EVAL-BANKING-001' WHERE [TransactionsId]=1;
GO

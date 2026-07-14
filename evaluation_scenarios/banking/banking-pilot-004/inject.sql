INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-BANKING-004','Open','Synthetic pilot defect for BAT-3104','EVAL-BANKING-004'); UPDATE eval.[payment_instructions] SET Status='Exception',Details='EVAL-BANKING-004' WHERE [PaymentInstructionsId]=1;
GO

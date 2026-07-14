INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-CLINIC-004','Open','Synthetic pilot defect for ENC-5504','EVAL-CLINIC-004'); UPDATE eval.[procedures_performed] SET Status='Exception',Details='EVAL-CLINIC-004' WHERE [ProceduresPerformedId]=1;
GO

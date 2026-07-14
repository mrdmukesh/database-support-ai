INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-CLINIC-001','Open','Synthetic pilot defect for APT-2101','EVAL-CLINIC-001'); UPDATE eval.[appointments] SET Status='Exception',Details='EVAL-CLINIC-001' WHERE [AppointmentsId]=1;
GO

INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-PAYROLL-001','Open','Synthetic pilot defect for EMP-1042','EVAL-PAYROLL-001'); UPDATE eval.[pay_groups] SET Status='Exception',Details='EVAL-PAYROLL-001' WHERE [PayGroupsId]=1;
GO

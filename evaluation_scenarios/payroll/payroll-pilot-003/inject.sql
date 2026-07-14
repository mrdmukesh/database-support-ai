INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-PAYROLL-003','Open','Synthetic pilot defect for PAY-7003','EVAL-PAYROLL-003'); UPDATE eval.[time_entries] SET Status='Exception',Details='EVAL-PAYROLL-003' WHERE [TimeEntriesId]=1;
GO

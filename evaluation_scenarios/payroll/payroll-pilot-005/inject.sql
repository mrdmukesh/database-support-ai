INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-PAYROLL-005','Open','Synthetic pilot defect for TAX-2026-07','EVAL-PAYROLL-005'); UPDATE eval.[payroll_runs] SET Status='Exception',Details='EVAL-PAYROLL-005' WHERE [PayrollRunsId]=1;
GO

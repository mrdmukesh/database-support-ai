INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-PAYROLL-002','Open','Synthetic pilot defect for RUN-2026-07-A','EVAL-PAYROLL-002'); UPDATE eval.[pay_periods] SET Status='Exception',Details='EVAL-PAYROLL-002' WHERE [PayPeriodsId]=1;
GO

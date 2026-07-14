INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('EVAL-PAYROLL-004','Open','Synthetic pilot defect for TIME-8821','EVAL-PAYROLL-004'); UPDATE eval.[leave_requests] SET Status='Exception',Details='EVAL-PAYROLL-004' WHERE [LeaveRequestsId]=1;
GO

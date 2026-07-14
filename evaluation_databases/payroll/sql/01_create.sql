SET XACT_ABORT ON;
GO
CREATE SCHEMA eval AUTHORIZATION dbo;
GO
CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);
INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'payroll',DB_NAME(),1);
GO
CREATE TABLE eval.[departments] (
  [DepartmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_departments_BusinessKey ON eval.[departments] (BusinessKey);
CREATE INDEX IX_departments_Status_EventTime ON eval.[departments] (Status, EventTime);
GO
CREATE TABLE eval.[employees] (
  [EmployeesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [DepartmentsId] BIGINT NULL REFERENCES eval.[departments]([DepartmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_employees_BusinessKey ON eval.[employees] (BusinessKey);
CREATE INDEX IX_employees_Status_EventTime ON eval.[employees] (Status, EventTime);
GO
CREATE TABLE eval.[employment_history] (
  [EmploymentHistoryId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EmployeesId] BIGINT NULL REFERENCES eval.[employees]([EmployeesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_employment_history_BusinessKey ON eval.[employment_history] (BusinessKey);
CREATE INDEX IX_employment_history_Status_EventTime ON eval.[employment_history] (Status, EventTime);
GO
CREATE TABLE eval.[pay_groups] (
  [PayGroupsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_pay_groups_BusinessKey ON eval.[pay_groups] (BusinessKey);
CREATE INDEX IX_pay_groups_Status_EventTime ON eval.[pay_groups] (Status, EventTime);
GO
CREATE TABLE eval.[pay_periods] (
  [PayPeriodsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PayGroupsId] BIGINT NULL REFERENCES eval.[pay_groups]([PayGroupsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_pay_periods_BusinessKey ON eval.[pay_periods] (BusinessKey);
CREATE INDEX IX_pay_periods_Status_EventTime ON eval.[pay_periods] (Status, EventTime);
GO
CREATE TABLE eval.[time_entries] (
  [TimeEntriesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EmployeesId] BIGINT NULL REFERENCES eval.[employees]([EmployeesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_time_entries_BusinessKey ON eval.[time_entries] (BusinessKey);
CREATE INDEX IX_time_entries_Status_EventTime ON eval.[time_entries] (Status, EventTime);
GO
CREATE TABLE eval.[leave_requests] (
  [LeaveRequestsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EmployeesId] BIGINT NULL REFERENCES eval.[employees]([EmployeesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_leave_requests_BusinessKey ON eval.[leave_requests] (BusinessKey);
CREATE INDEX IX_leave_requests_Status_EventTime ON eval.[leave_requests] (Status, EventTime);
GO
CREATE TABLE eval.[payroll_runs] (
  [PayrollRunsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PayPeriodsId] BIGINT NULL REFERENCES eval.[pay_periods]([PayPeriodsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_payroll_runs_BusinessKey ON eval.[payroll_runs] (BusinessKey);
CREATE INDEX IX_payroll_runs_Status_EventTime ON eval.[payroll_runs] (Status, EventTime);
GO
CREATE TABLE eval.[payroll_items] (
  [PayrollItemsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PayrollRunsId] BIGINT NULL REFERENCES eval.[payroll_runs]([PayrollRunsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_payroll_items_BusinessKey ON eval.[payroll_items] (BusinessKey);
CREATE INDEX IX_payroll_items_Status_EventTime ON eval.[payroll_items] (Status, EventTime);
GO
CREATE TABLE eval.[deductions] (
  [DeductionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EmployeesId] BIGINT NULL REFERENCES eval.[employees]([EmployeesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_deductions_BusinessKey ON eval.[deductions] (BusinessKey);
CREATE INDEX IX_deductions_Status_EventTime ON eval.[deductions] (Status, EventTime);
GO
CREATE TABLE eval.[payments] (
  [PaymentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PayrollItemsId] BIGINT NULL REFERENCES eval.[payroll_items]([PayrollItemsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_payments_BusinessKey ON eval.[payments] (BusinessKey);
CREATE INDEX IX_payments_Status_EventTime ON eval.[payments] (Status, EventTime);
GO
CREATE TABLE eval.[tax_filings] (
  [TaxFilingsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PayrollRunsId] BIGINT NULL REFERENCES eval.[payroll_runs]([PayrollRunsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_tax_filings_BusinessKey ON eval.[tax_filings] (BusinessKey);
CREATE INDEX IX_tax_filings_Status_EventTime ON eval.[tax_filings] (Status, EventTime);
GO
CREATE TABLE eval.[integration_messages] (
  [IntegrationMessagesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_integration_messages_BusinessKey ON eval.[integration_messages] (BusinessKey);
CREATE INDEX IX_integration_messages_Status_EventTime ON eval.[integration_messages] (Status, EventTime);
GO
CREATE TABLE eval.[batch_runs] (
  [BatchRunsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_batch_runs_BusinessKey ON eval.[batch_runs] (BusinessKey);
CREATE INDEX IX_batch_runs_Status_EventTime ON eval.[batch_runs] (Status, EventTime);
GO
CREATE TABLE eval.[exceptions] (
  [ExceptionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_exceptions_BusinessKey ON eval.[exceptions] (BusinessKey);
CREATE INDEX IX_exceptions_Status_EventTime ON eval.[exceptions] (Status, EventTime);
GO
CREATE TABLE eval.[audit_history] (
  [AuditHistoryId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_audit_history_BusinessKey ON eval.[audit_history] (BusinessKey);
CREATE INDEX IX_audit_history_Status_EventTime ON eval.[audit_history] (Status, EventTime);
GO
CREATE VIEW eval.vw_payroll_operations_1 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[employment_history] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_payroll_operations_2 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[pay_groups] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_payroll_operations_3 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[pay_periods] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_payroll_operations_4 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[time_entries] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_payroll_operations_5 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[leave_requests] WHERE IsActive = 1;
GO
CREATE FUNCTION eval.fn_payroll_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_1 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[pay_groups] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_2 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[pay_periods] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_3 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[time_entries] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_4 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[leave_requests] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_5 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[payroll_runs] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_6 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[payroll_items] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_7 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[deductions] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_payroll_workflow_8 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[payments] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE TRIGGER eval.tr_employees_audit ON eval.[employees] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;
GO

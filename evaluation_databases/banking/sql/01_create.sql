SET XACT_ABORT ON;
GO
CREATE SCHEMA eval AUTHORIZATION dbo;
GO
CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);
INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'banking',DB_NAME(),1);
GO
CREATE TABLE eval.[customers] (
  [CustomersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_customers_BusinessKey ON eval.[customers] (BusinessKey);
CREATE INDEX IX_customers_Status_EventTime ON eval.[customers] (Status, EventTime);
GO
CREATE TABLE eval.[accounts] (
  [AccountsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_accounts_BusinessKey ON eval.[accounts] (BusinessKey);
CREATE INDEX IX_accounts_Status_EventTime ON eval.[accounts] (Status, EventTime);
GO
CREATE TABLE eval.[account_balances] (
  [AccountBalancesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AccountsId] BIGINT NULL REFERENCES eval.[accounts]([AccountsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_account_balances_BusinessKey ON eval.[account_balances] (BusinessKey);
CREATE INDEX IX_account_balances_Status_EventTime ON eval.[account_balances] (Status, EventTime);
GO
CREATE TABLE eval.[transactions] (
  [TransactionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AccountsId] BIGINT NULL REFERENCES eval.[accounts]([AccountsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_transactions_BusinessKey ON eval.[transactions] (BusinessKey);
CREATE INDEX IX_transactions_Status_EventTime ON eval.[transactions] (Status, EventTime);
GO
CREATE TABLE eval.[transfers] (
  [TransfersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AccountsId] BIGINT NULL REFERENCES eval.[accounts]([AccountsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_transfers_BusinessKey ON eval.[transfers] (BusinessKey);
CREATE INDEX IX_transfers_Status_EventTime ON eval.[transfers] (Status, EventTime);
GO
CREATE TABLE eval.[beneficiaries] (
  [BeneficiariesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_beneficiaries_BusinessKey ON eval.[beneficiaries] (BusinessKey);
CREATE INDEX IX_beneficiaries_Status_EventTime ON eval.[beneficiaries] (Status, EventTime);
GO
CREATE TABLE eval.[payment_instructions] (
  [PaymentInstructionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AccountsId] BIGINT NULL REFERENCES eval.[accounts]([AccountsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_payment_instructions_BusinessKey ON eval.[payment_instructions] (BusinessKey);
CREATE INDEX IX_payment_instructions_Status_EventTime ON eval.[payment_instructions] (Status, EventTime);
GO
CREATE TABLE eval.[loans] (
  [LoansId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_loans_BusinessKey ON eval.[loans] (BusinessKey);
CREATE INDEX IX_loans_Status_EventTime ON eval.[loans] (Status, EventTime);
GO
CREATE TABLE eval.[loan_schedules] (
  [LoanSchedulesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [LoansId] BIGINT NULL REFERENCES eval.[loans]([LoansId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_loan_schedules_BusinessKey ON eval.[loan_schedules] (BusinessKey);
CREATE INDEX IX_loan_schedules_Status_EventTime ON eval.[loan_schedules] (Status, EventTime);
GO
CREATE TABLE eval.[cards] (
  [CardsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AccountsId] BIGINT NULL REFERENCES eval.[accounts]([AccountsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_cards_BusinessKey ON eval.[cards] (BusinessKey);
CREATE INDEX IX_cards_Status_EventTime ON eval.[cards] (Status, EventTime);
GO
CREATE TABLE eval.[fraud_alerts] (
  [FraudAlertsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [TransactionsId] BIGINT NULL REFERENCES eval.[transactions]([TransactionsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_fraud_alerts_BusinessKey ON eval.[fraud_alerts] (BusinessKey);
CREATE INDEX IX_fraud_alerts_Status_EventTime ON eval.[fraud_alerts] (Status, EventTime);
GO
CREATE TABLE eval.[compliance_cases] (
  [ComplianceCasesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_compliance_cases_BusinessKey ON eval.[compliance_cases] (BusinessKey);
CREATE INDEX IX_compliance_cases_Status_EventTime ON eval.[compliance_cases] (Status, EventTime);
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
CREATE VIEW eval.vw_banking_operations_1 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[account_balances] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_banking_operations_2 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[transactions] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_banking_operations_3 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[transfers] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_banking_operations_4 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[beneficiaries] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_banking_operations_5 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[payment_instructions] WHERE IsActive = 1;
GO
CREATE FUNCTION eval.fn_banking_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_1 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[transactions] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_2 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[transfers] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_3 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[beneficiaries] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_4 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[payment_instructions] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_5 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[loans] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_6 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[loan_schedules] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_7 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[cards] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_banking_workflow_8 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[fraud_alerts] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE TRIGGER eval.tr_accounts_audit ON eval.[accounts] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;
GO

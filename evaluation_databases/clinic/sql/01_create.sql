SET XACT_ABORT ON;
GO
CREATE SCHEMA eval AUTHORIZATION dbo;
GO
CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);
INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'clinic',DB_NAME(),1);
GO
CREATE TABLE eval.[clinics] (
  [ClinicsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_clinics_BusinessKey ON eval.[clinics] (BusinessKey);
CREATE INDEX IX_clinics_Status_EventTime ON eval.[clinics] (Status, EventTime);
GO
CREATE TABLE eval.[providers] (
  [ProvidersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ClinicsId] BIGINT NULL REFERENCES eval.[clinics]([ClinicsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_providers_BusinessKey ON eval.[providers] (BusinessKey);
CREATE INDEX IX_providers_Status_EventTime ON eval.[providers] (Status, EventTime);
GO
CREATE TABLE eval.[patients] (
  [PatientsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_patients_BusinessKey ON eval.[patients] (BusinessKey);
CREATE INDEX IX_patients_Status_EventTime ON eval.[patients] (Status, EventTime);
GO
CREATE TABLE eval.[appointments] (
  [AppointmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PatientsId] BIGINT NULL REFERENCES eval.[patients]([PatientsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_appointments_BusinessKey ON eval.[appointments] (BusinessKey);
CREATE INDEX IX_appointments_Status_EventTime ON eval.[appointments] (Status, EventTime);
GO
CREATE TABLE eval.[encounters] (
  [EncountersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AppointmentsId] BIGINT NULL REFERENCES eval.[appointments]([AppointmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_encounters_BusinessKey ON eval.[encounters] (BusinessKey);
CREATE INDEX IX_encounters_Status_EventTime ON eval.[encounters] (Status, EventTime);
GO
CREATE TABLE eval.[diagnoses] (
  [DiagnosesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EncountersId] BIGINT NULL REFERENCES eval.[encounters]([EncountersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_diagnoses_BusinessKey ON eval.[diagnoses] (BusinessKey);
CREATE INDEX IX_diagnoses_Status_EventTime ON eval.[diagnoses] (Status, EventTime);
GO
CREATE TABLE eval.[procedures_performed] (
  [ProceduresPerformedId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EncountersId] BIGINT NULL REFERENCES eval.[encounters]([EncountersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_procedures_performed_BusinessKey ON eval.[procedures_performed] (BusinessKey);
CREATE INDEX IX_procedures_performed_Status_EventTime ON eval.[procedures_performed] (Status, EventTime);
GO
CREATE TABLE eval.[prescriptions] (
  [PrescriptionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EncountersId] BIGINT NULL REFERENCES eval.[encounters]([EncountersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_prescriptions_BusinessKey ON eval.[prescriptions] (BusinessKey);
CREATE INDEX IX_prescriptions_Status_EventTime ON eval.[prescriptions] (Status, EventTime);
GO
CREATE TABLE eval.[lab_orders] (
  [LabOrdersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EncountersId] BIGINT NULL REFERENCES eval.[encounters]([EncountersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_lab_orders_BusinessKey ON eval.[lab_orders] (BusinessKey);
CREATE INDEX IX_lab_orders_Status_EventTime ON eval.[lab_orders] (Status, EventTime);
GO
CREATE TABLE eval.[lab_results] (
  [LabResultsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [LabOrdersId] BIGINT NULL REFERENCES eval.[lab_orders]([LabOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_lab_results_BusinessKey ON eval.[lab_results] (BusinessKey);
CREATE INDEX IX_lab_results_Status_EventTime ON eval.[lab_results] (Status, EventTime);
GO
CREATE TABLE eval.[insurance_policies] (
  [InsurancePoliciesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PatientsId] BIGINT NULL REFERENCES eval.[patients]([PatientsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_insurance_policies_BusinessKey ON eval.[insurance_policies] (BusinessKey);
CREATE INDEX IX_insurance_policies_Status_EventTime ON eval.[insurance_policies] (Status, EventTime);
GO
CREATE TABLE eval.[claims] (
  [ClaimsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [EncountersId] BIGINT NULL REFERENCES eval.[encounters]([EncountersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_claims_BusinessKey ON eval.[claims] (BusinessKey);
CREATE INDEX IX_claims_Status_EventTime ON eval.[claims] (Status, EventTime);
GO
CREATE TABLE eval.[payments] (
  [PaymentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ClaimsId] BIGINT NULL REFERENCES eval.[claims]([ClaimsId]),
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
CREATE VIEW eval.vw_clinic_operations_1 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[patients] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_clinic_operations_2 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[appointments] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_clinic_operations_3 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[encounters] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_clinic_operations_4 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[diagnoses] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_clinic_operations_5 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[procedures_performed] WHERE IsActive = 1;
GO
CREATE FUNCTION eval.fn_clinic_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_1 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[appointments] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_2 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[encounters] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_3 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[diagnoses] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_4 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[procedures_performed] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_5 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[prescriptions] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_6 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[lab_orders] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_7 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[lab_results] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_clinic_workflow_8 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[insurance_policies] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE TRIGGER eval.tr_providers_audit ON eval.[providers] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;
GO

SET XACT_ABORT ON;
GO
CREATE SCHEMA eval AUTHORIZATION dbo;
GO
CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);
INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'shipping',DB_NAME(),1);
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
CREATE TABLE eval.[bookings] (
  [BookingsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_bookings_BusinessKey ON eval.[bookings] (BusinessKey);
CREATE INDEX IX_bookings_Status_EventTime ON eval.[bookings] (Status, EventTime);
GO
CREATE TABLE eval.[shipments] (
  [ShipmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BookingsId] BIGINT NULL REFERENCES eval.[bookings]([BookingsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_shipments_BusinessKey ON eval.[shipments] (BusinessKey);
CREATE INDEX IX_shipments_Status_EventTime ON eval.[shipments] (Status, EventTime);
GO
CREATE TABLE eval.[bills_of_lading] (
  [BillsOfLadingId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_bills_of_lading_BusinessKey ON eval.[bills_of_lading] (BusinessKey);
CREATE INDEX IX_bills_of_lading_Status_EventTime ON eval.[bills_of_lading] (Status, EventTime);
GO
CREATE TABLE eval.[container_master] (
  [ContainerMasterId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_container_master_BusinessKey ON eval.[container_master] (BusinessKey);
CREATE INDEX IX_container_master_Status_EventTime ON eval.[container_master] (Status, EventTime);
GO
CREATE TABLE eval.[container_assignments] (
  [ContainerAssignmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_container_assignments_BusinessKey ON eval.[container_assignments] (BusinessKey);
CREATE INDEX IX_container_assignments_Status_EventTime ON eval.[container_assignments] (Status, EventTime);
GO
CREATE TABLE eval.[vessels] (
  [VesselsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_vessels_BusinessKey ON eval.[vessels] (BusinessKey);
CREATE INDEX IX_vessels_Status_EventTime ON eval.[vessels] (Status, EventTime);
GO
CREATE TABLE eval.[voyages] (
  [VoyagesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [VesselsId] BIGINT NULL REFERENCES eval.[vessels]([VesselsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_voyages_BusinessKey ON eval.[voyages] (BusinessKey);
CREATE INDEX IX_voyages_Status_EventTime ON eval.[voyages] (Status, EventTime);
GO
CREATE TABLE eval.[ports] (
  [PortsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_ports_BusinessKey ON eval.[ports] (BusinessKey);
CREATE INDEX IX_ports_Status_EventTime ON eval.[ports] (Status, EventTime);
GO
CREATE TABLE eval.[terminals] (
  [TerminalsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PortsId] BIGINT NULL REFERENCES eval.[ports]([PortsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_terminals_BusinessKey ON eval.[terminals] (BusinessKey);
CREATE INDEX IX_terminals_Status_EventTime ON eval.[terminals] (Status, EventTime);
GO
CREATE TABLE eval.[depots] (
  [DepotsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PortsId] BIGINT NULL REFERENCES eval.[ports]([PortsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_depots_BusinessKey ON eval.[depots] (BusinessKey);
CREATE INDEX IX_depots_Status_EventTime ON eval.[depots] (Status, EventTime);
GO
CREATE TABLE eval.[container_events] (
  [ContainerEventsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_container_events_BusinessKey ON eval.[container_events] (BusinessKey);
CREATE INDEX IX_container_events_Status_EventTime ON eval.[container_events] (Status, EventTime);
GO
CREATE TABLE eval.[shipment_milestones] (
  [ShipmentMilestonesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_shipment_milestones_BusinessKey ON eval.[shipment_milestones] (BusinessKey);
CREATE INDEX IX_shipment_milestones_Status_EventTime ON eval.[shipment_milestones] (Status, EventTime);
GO
CREATE TABLE eval.[transport_work_orders] (
  [TransportWorkOrdersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_transport_work_orders_BusinessKey ON eval.[transport_work_orders] (BusinessKey);
CREATE INDEX IX_transport_work_orders_Status_EventTime ON eval.[transport_work_orders] (Status, EventTime);
GO
CREATE TABLE eval.[carrier_assignments] (
  [CarrierAssignmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [TransportWorkOrdersId] BIGINT NULL REFERENCES eval.[transport_work_orders]([TransportWorkOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_carrier_assignments_BusinessKey ON eval.[carrier_assignments] (BusinessKey);
CREATE INDEX IX_carrier_assignments_Status_EventTime ON eval.[carrier_assignments] (Status, EventTime);
GO
CREATE TABLE eval.[truck_movements] (
  [TruckMovementsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [TransportWorkOrdersId] BIGINT NULL REFERENCES eval.[transport_work_orders]([TransportWorkOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_truck_movements_BusinessKey ON eval.[truck_movements] (BusinessKey);
CREATE INDEX IX_truck_movements_Status_EventTime ON eval.[truck_movements] (Status, EventTime);
GO
CREATE TABLE eval.[rail_movements] (
  [RailMovementsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [TransportWorkOrdersId] BIGINT NULL REFERENCES eval.[transport_work_orders]([TransportWorkOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_rail_movements_BusinessKey ON eval.[rail_movements] (BusinessKey);
CREATE INDEX IX_rail_movements_Status_EventTime ON eval.[rail_movements] (Status, EventTime);
GO
CREATE TABLE eval.[vessel_movements] (
  [VesselMovementsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [VoyagesId] BIGINT NULL REFERENCES eval.[voyages]([VoyagesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_vessel_movements_BusinessKey ON eval.[vessel_movements] (BusinessKey);
CREATE INDEX IX_vessel_movements_Status_EventTime ON eval.[vessel_movements] (Status, EventTime);
GO
CREATE TABLE eval.[gate_transactions] (
  [GateTransactionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_gate_transactions_BusinessKey ON eval.[gate_transactions] (BusinessKey);
CREATE INDEX IX_gate_transactions_Status_EventTime ON eval.[gate_transactions] (Status, EventTime);
GO
CREATE TABLE eval.[equipment_interchange] (
  [EquipmentInterchangeId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [GateTransactionsId] BIGINT NULL REFERENCES eval.[gate_transactions]([GateTransactionsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_equipment_interchange_BusinessKey ON eval.[equipment_interchange] (BusinessKey);
CREATE INDEX IX_equipment_interchange_Status_EventTime ON eval.[equipment_interchange] (Status, EventTime);
GO
CREATE TABLE eval.[customs_holds] (
  [CustomsHoldsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_customs_holds_BusinessKey ON eval.[customs_holds] (BusinessKey);
CREATE INDEX IX_customs_holds_Status_EventTime ON eval.[customs_holds] (Status, EventTime);
GO
CREATE TABLE eval.[customs_releases] (
  [CustomsReleasesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomsHoldsId] BIGINT NULL REFERENCES eval.[customs_holds]([CustomsHoldsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_customs_releases_BusinessKey ON eval.[customs_releases] (BusinessKey);
CREATE INDEX IX_customs_releases_Status_EventTime ON eval.[customs_releases] (Status, EventTime);
GO
CREATE TABLE eval.[dangerous_goods] (
  [DangerousGoodsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_dangerous_goods_BusinessKey ON eval.[dangerous_goods] (BusinessKey);
CREATE INDEX IX_dangerous_goods_Status_EventTime ON eval.[dangerous_goods] (Status, EventTime);
GO
CREATE TABLE eval.[reefer_settings] (
  [ReeferSettingsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_reefer_settings_BusinessKey ON eval.[reefer_settings] (BusinessKey);
CREATE INDEX IX_reefer_settings_Status_EventTime ON eval.[reefer_settings] (Status, EventTime);
GO
CREATE TABLE eval.[reefer_readings] (
  [ReeferReadingsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ReeferSettingsId] BIGINT NULL REFERENCES eval.[reefer_settings]([ReeferSettingsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_reefer_readings_BusinessKey ON eval.[reefer_readings] (BusinessKey);
CREATE INDEX IX_reefer_readings_Status_EventTime ON eval.[reefer_readings] (Status, EventTime);
GO
CREATE TABLE eval.[damage_reports] (
  [DamageReportsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_damage_reports_BusinessKey ON eval.[damage_reports] (BusinessKey);
CREATE INDEX IX_damage_reports_Status_EventTime ON eval.[damage_reports] (Status, EventTime);
GO
CREATE TABLE eval.[repair_orders] (
  [RepairOrdersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [DamageReportsId] BIGINT NULL REFERENCES eval.[damage_reports]([DamageReportsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_repair_orders_BusinessKey ON eval.[repair_orders] (BusinessKey);
CREATE INDEX IX_repair_orders_Status_EventTime ON eval.[repair_orders] (Status, EventTime);
GO
CREATE TABLE eval.[empty_return_instructions] (
  [EmptyReturnInstructionsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_empty_return_instructions_BusinessKey ON eval.[empty_return_instructions] (BusinessKey);
CREATE INDEX IX_empty_return_instructions_Status_EventTime ON eval.[empty_return_instructions] (Status, EventTime);
GO
CREATE TABLE eval.[demurrage_detention] (
  [DemurrageDetentionId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ContainerAssignmentsId] BIGINT NULL REFERENCES eval.[container_assignments]([ContainerAssignmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_demurrage_detention_BusinessKey ON eval.[demurrage_detention] (BusinessKey);
CREATE INDEX IX_demurrage_detention_Status_EventTime ON eval.[demurrage_detention] (Status, EventTime);
GO
CREATE TABLE eval.[invoices] (
  [InvoicesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ShipmentsId] BIGINT NULL REFERENCES eval.[shipments]([ShipmentsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_invoices_BusinessKey ON eval.[invoices] (BusinessKey);
CREATE INDEX IX_invoices_Status_EventTime ON eval.[invoices] (Status, EventTime);
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
CREATE VIEW eval.vw_shipping_operations_1 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[shipments] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_shipping_operations_2 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[bills_of_lading] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_shipping_operations_3 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[container_master] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_shipping_operations_4 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[container_assignments] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_shipping_operations_5 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[vessels] WHERE IsActive = 1;
GO
CREATE FUNCTION eval.fn_shipping_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_1 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[bills_of_lading] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_2 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[container_master] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_3 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[container_assignments] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_4 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[vessels] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_5 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[voyages] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_6 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[ports] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_7 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[terminals] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_shipping_workflow_8 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[depots] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE TRIGGER eval.tr_bookings_audit ON eval.[bookings] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;
GO

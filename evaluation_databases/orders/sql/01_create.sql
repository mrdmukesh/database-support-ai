SET XACT_ABORT ON;
GO
CREATE SCHEMA eval AUTHORIZATION dbo;
GO
CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);
INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'orders',DB_NAME(),1);
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
CREATE TABLE eval.[products] (
  [ProductsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_products_BusinessKey ON eval.[products] (BusinessKey);
CREATE INDEX IX_products_Status_EventTime ON eval.[products] (Status, EventTime);
GO
CREATE TABLE eval.[warehouses] (
  [WarehousesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_warehouses_BusinessKey ON eval.[warehouses] (BusinessKey);
CREATE INDEX IX_warehouses_Status_EventTime ON eval.[warehouses] (Status, EventTime);
GO
CREATE TABLE eval.[inventory_balances] (
  [InventoryBalancesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [ProductsId] BIGINT NULL REFERENCES eval.[products]([ProductsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_inventory_balances_BusinessKey ON eval.[inventory_balances] (BusinessKey);
CREATE INDEX IX_inventory_balances_Status_EventTime ON eval.[inventory_balances] (Status, EventTime);
GO
CREATE TABLE eval.[inventory_movements] (
  [InventoryMovementsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [InventoryBalancesId] BIGINT NULL REFERENCES eval.[inventory_balances]([InventoryBalancesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_inventory_movements_BusinessKey ON eval.[inventory_movements] (BusinessKey);
CREATE INDEX IX_inventory_movements_Status_EventTime ON eval.[inventory_movements] (Status, EventTime);
GO
CREATE TABLE eval.[sales_orders] (
  [SalesOrdersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomersId] BIGINT NULL REFERENCES eval.[customers]([CustomersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_sales_orders_BusinessKey ON eval.[sales_orders] (BusinessKey);
CREATE INDEX IX_sales_orders_Status_EventTime ON eval.[sales_orders] (Status, EventTime);
GO
CREATE TABLE eval.[sales_order_lines] (
  [SalesOrderLinesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [SalesOrdersId] BIGINT NULL REFERENCES eval.[sales_orders]([SalesOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_sales_order_lines_BusinessKey ON eval.[sales_order_lines] (BusinessKey);
CREATE INDEX IX_sales_order_lines_Status_EventTime ON eval.[sales_order_lines] (Status, EventTime);
GO
CREATE TABLE eval.[allocations] (
  [AllocationsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [SalesOrderLinesId] BIGINT NULL REFERENCES eval.[sales_order_lines]([SalesOrderLinesId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_allocations_BusinessKey ON eval.[allocations] (BusinessKey);
CREATE INDEX IX_allocations_Status_EventTime ON eval.[allocations] (Status, EventTime);
GO
CREATE TABLE eval.[pick_tasks] (
  [PickTasksId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [AllocationsId] BIGINT NULL REFERENCES eval.[allocations]([AllocationsId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_pick_tasks_BusinessKey ON eval.[pick_tasks] (BusinessKey);
CREATE INDEX IX_pick_tasks_Status_EventTime ON eval.[pick_tasks] (Status, EventTime);
GO
CREATE TABLE eval.[shipments] (
  [ShipmentsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [SalesOrdersId] BIGINT NULL REFERENCES eval.[sales_orders]([SalesOrdersId]),
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
CREATE TABLE eval.[purchase_orders] (
  [PurchaseOrdersId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_purchase_orders_BusinessKey ON eval.[purchase_orders] (BusinessKey);
CREATE INDEX IX_purchase_orders_Status_EventTime ON eval.[purchase_orders] (Status, EventTime);
GO
CREATE TABLE eval.[purchase_order_lines] (
  [PurchaseOrderLinesId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PurchaseOrdersId] BIGINT NULL REFERENCES eval.[purchase_orders]([PurchaseOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_purchase_order_lines_BusinessKey ON eval.[purchase_order_lines] (BusinessKey);
CREATE INDEX IX_purchase_order_lines_Status_EventTime ON eval.[purchase_order_lines] (Status, EventTime);
GO
CREATE TABLE eval.[receipts] (
  [ReceiptsId] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [PurchaseOrdersId] BIGINT NULL REFERENCES eval.[purchase_orders]([PurchaseOrdersId]),
  [BusinessKey] NVARCHAR(80) NOT NULL,
  [Status] NVARCHAR(40) NOT NULL,
  [EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  [Details] NVARCHAR(1000) NULL,
  [CorrelationId] NVARCHAR(80) NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);
GO
CREATE UNIQUE INDEX UX_receipts_BusinessKey ON eval.[receipts] (BusinessKey);
CREATE INDEX IX_receipts_Status_EventTime ON eval.[receipts] (Status, EventTime);
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
CREATE VIEW eval.vw_orders_operations_1 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[warehouses] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_orders_operations_2 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[inventory_balances] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_orders_operations_3 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[inventory_movements] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_orders_operations_4 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[sales_orders] WHERE IsActive = 1;
GO
CREATE VIEW eval.vw_orders_operations_5 AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[sales_order_lines] WHERE IsActive = 1;
GO
CREATE FUNCTION eval.fn_orders_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_1 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[inventory_balances] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_2 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[inventory_movements] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_3 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[sales_orders] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_4 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[sales_order_lines] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_5 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[allocations] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_6 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[pick_tasks] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_7 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[shipments] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE PROCEDURE eval.usp_orders_workflow_8 @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[purchase_orders] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;
GO
CREATE TRIGGER eval.tr_products_audit ON eval.[products] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;
GO

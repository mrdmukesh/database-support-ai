# ruff: noqa: E501
"""Generate deterministic, synthetic Azure SQL evaluation database packages."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAINS = {
    "payroll": {
        "title": "Employee Payroll",
        "tables": [
            ("departments", None),
            ("employees", "departments"),
            ("employment_history", "employees"),
            ("pay_groups", None),
            ("pay_periods", "pay_groups"),
            ("time_entries", "employees"),
            ("leave_requests", "employees"),
            ("payroll_runs", "pay_periods"),
            ("payroll_items", "payroll_runs"),
            ("deductions", "employees"),
            ("payments", "payroll_items"),
            ("tax_filings", "payroll_runs"),
            ("integration_messages", None),
            ("batch_runs", None),
            ("exceptions", None),
            ("audit_history", None),
        ],
        "entities": ["EMP-1042", "RUN-2026-07-A", "PAY-7003", "TIME-8821", "TAX-2026-07"],
        "questions": [
            "Why is employee EMP-1042 missing from payroll run RUN-2026-07-A?",
            "Why was payment PAY-7003 produced twice?",
            "Why were overtime hours from TIME-8821 not included?",
            "Why does payroll run RUN-2026-07-A remain Processing?",
            "Is there enough evidence to confirm TAX-2026-07 was filed late?",
        ],
    },
    "clinic": {
        "title": "Clinic Operations",
        "tables": [
            ("clinics", None),
            ("providers", "clinics"),
            ("patients", None),
            ("appointments", "patients"),
            ("encounters", "appointments"),
            ("diagnoses", "encounters"),
            ("procedures_performed", "encounters"),
            ("prescriptions", "encounters"),
            ("lab_orders", "encounters"),
            ("lab_results", "lab_orders"),
            ("insurance_policies", "patients"),
            ("claims", "encounters"),
            ("payments", "claims"),
            ("integration_messages", None),
            ("exceptions", None),
            ("audit_history", None),
        ],
        "entities": ["APT-2101", "CLM-3302", "LAB-4403", "ENC-5504", "PAT-6605"],
        "questions": [
            "Why was appointment APT-2101 not converted into an encounter?",
            "Why was claim CLM-3302 submitted twice?",
            "Why is lab result LAB-4403 not visible on its encounter?",
            "Why does encounter ENC-5504 remain Open after checkout?",
            "Is there enough evidence to confirm patient PAT-6605 missed an appointment?",
        ],
    },
    "orders": {
        "title": "Order and Inventory Management",
        "tables": [
            ("customers", None),
            ("products", None),
            ("warehouses", None),
            ("inventory_balances", "products"),
            ("inventory_movements", "inventory_balances"),
            ("sales_orders", "customers"),
            ("sales_order_lines", "sales_orders"),
            ("allocations", "sales_order_lines"),
            ("pick_tasks", "allocations"),
            ("shipments", "sales_orders"),
            ("purchase_orders", None),
            ("purchase_order_lines", "purchase_orders"),
            ("receipts", "purchase_orders"),
            ("integration_messages", None),
            ("batch_runs", None),
            ("exceptions", None),
            ("audit_history", None),
        ],
        "entities": ["ORD-7101", "ORD-7102", "SKU-8103", "PICK-9104", "PO-1205"],
        "questions": [
            "Why was order ORD-7101 not allocated despite available inventory?",
            "Why was order ORD-7102 imported twice?",
            "Why is SKU-8103 showing a negative available balance?",
            "Why does pick task PICK-9104 remain In Progress after shipment?",
            "Is there enough evidence to confirm purchase order PO-1205 arrived late?",
        ],
    },
    "banking": {
        "title": "Banking Operations",
        "tables": [
            ("customers", None),
            ("accounts", "customers"),
            ("account_balances", "accounts"),
            ("transactions", "accounts"),
            ("transfers", "accounts"),
            ("beneficiaries", "customers"),
            ("payment_instructions", "accounts"),
            ("loans", "customers"),
            ("loan_schedules", "loans"),
            ("cards", "accounts"),
            ("fraud_alerts", "transactions"),
            ("compliance_cases", "customers"),
            ("integration_messages", None),
            ("batch_runs", None),
            ("exceptions", None),
            ("audit_history", None),
        ],
        "entities": ["TRF-3101", "PMT-3102", "ACC-3103", "BAT-3104", "TXN-3105"],
        "questions": [
            "Why is transfer TRF-3101 completed without a matching balance movement?",
            "Why was payment instruction PMT-3102 posted twice?",
            "Why was account ACC-3103 charged by an inactive beneficiary?",
            "Why does settlement batch BAT-3104 remain Running?",
            "Is there enough evidence to confirm transaction TXN-3105 was fraudulent?",
        ],
    },
    "shipping": {
        "title": "Shipping and Container Operations",
        "tables": [
            ("customers", None),
            ("bookings", "customers"),
            ("shipments", "bookings"),
            ("bills_of_lading", "shipments"),
            ("container_master", None),
            ("container_assignments", "shipments"),
            ("vessels", None),
            ("voyages", "vessels"),
            ("ports", None),
            ("terminals", "ports"),
            ("depots", "ports"),
            ("container_events", "container_assignments"),
            ("shipment_milestones", "shipments"),
            ("transport_work_orders", "shipments"),
            ("carrier_assignments", "transport_work_orders"),
            ("truck_movements", "transport_work_orders"),
            ("rail_movements", "transport_work_orders"),
            ("vessel_movements", "voyages"),
            ("gate_transactions", "container_assignments"),
            ("equipment_interchange", "gate_transactions"),
            ("customs_holds", "shipments"),
            ("customs_releases", "customs_holds"),
            ("dangerous_goods", "shipments"),
            ("reefer_settings", "container_assignments"),
            ("reefer_readings", "reefer_settings"),
            ("damage_reports", "container_assignments"),
            ("repair_orders", "damage_reports"),
            ("empty_return_instructions", "container_assignments"),
            ("demurrage_detention", "container_assignments"),
            ("invoices", "shipments"),
            ("integration_messages", None),
            ("batch_runs", None),
            ("exceptions", None),
            ("audit_history", None),
        ],
        "entities": ["SHP-5001", "CONT-5002", "WO-5003", "SHP-5004", "CONT-5005"],
        "questions": [
            "Delivery is complete for shipment SHP-5001; why is the empty-return work order missing?",
            "Why does container CONT-5002 have a duplicate terminal gate event?",
            "Why was the wrong carrier selected for empty work order WO-5003?",
            "Why does shipment SHP-5004 remain In Transit after import discharge?",
            "Is there enough evidence to confirm container CONT-5005 was delayed?",
        ],
    },
}

ROOT_CAUSES = [
    "required downstream work item was not created after a completed upstream transition",
    "integration retry inserted the same business event without an idempotency guard",
    "selection used historical assignment instead of the active work item",
    "integration failure prevented the terminal status transition",
    "available timestamps do not establish the claimed delay",
]
RESPONSE_TYPES = [
    "confirmed_root_cause",
    "confirmed_root_cause",
    "confirmed_root_cause",
    "confirmed_root_cause",
    "insufficient_evidence",
]


def ident(name: str) -> str:
    return "".join(part.title() for part in name.split("_"))


def create_sql(domain: str, cfg: dict) -> str:
    lines = ["SET XACT_ABORT ON;", "GO", "CREATE SCHEMA eval AUTHORIZATION dbo;", "GO"]
    lines += [
        "CREATE TABLE eval.evaluation_marker (MarkerId INT NOT NULL PRIMARY KEY, DomainName NVARCHAR(40) NOT NULL, DatabaseName SYSNAME NOT NULL, IsSynthetic BIT NOT NULL);",
        f"INSERT eval.evaluation_marker(MarkerId,DomainName,DatabaseName,IsSynthetic) VALUES (1,'{domain}',DB_NAME(),1);",
        "GO",
    ]
    for table, parent in cfg["tables"]:
        table_id = f"{ident(table)}Id"
        cols = [
            f"[{table_id}] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY",
            "[BusinessKey] NVARCHAR(80) NOT NULL",
            "[Status] NVARCHAR(40) NOT NULL",
            "[EventTime] DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()",
            "[Details] NVARCHAR(1000) NULL",
            "[CorrelationId] NVARCHAR(80) NULL",
            "[IsActive] BIT NOT NULL DEFAULT 1",
        ]
        if parent:
            parent_id = f"{ident(parent)}Id"
            cols.insert(1, f"[{parent_id}] BIGINT NULL REFERENCES eval.[{parent}]([{parent_id}])")
        lines += [
            f"CREATE TABLE eval.[{table}] (\n  " + ",\n  ".join(cols) + "\n);",
            "GO",
            f"CREATE UNIQUE INDEX UX_{table}_BusinessKey ON eval.[{table}] (BusinessKey);",
            f"CREATE INDEX IX_{table}_Status_EventTime ON eval.[{table}] (Status, EventTime);",
            "GO",
        ]
    primary = cfg["tables"][1][0]
    for n in range(1, 6):
        lines += [
            f"CREATE VIEW eval.vw_{domain}_operations_{n} AS SELECT BusinessKey, Status, EventTime, Details FROM eval.[{cfg['tables'][(n + 1) % len(cfg['tables'])][0]}] WHERE IsActive = 1;",
            "GO",
        ]
    lines += [
        f"CREATE FUNCTION eval.fn_{domain}_active_status(@Status NVARCHAR(40)) RETURNS BIT AS BEGIN RETURN CASE WHEN @Status IN ('Active','Open','Processing','In Transit') THEN 1 ELSE 0 END; END;",
        "GO",
    ]
    for n in range(1, 9):
        table = cfg["tables"][(n + 2) % len(cfg["tables"])][0]
        lines += [
            f"CREATE PROCEDURE eval.usp_{domain}_workflow_{n} @BusinessKey NVARCHAR(80), @Status NVARCHAR(40) AS BEGIN SET NOCOUNT ON; UPDATE eval.[{table}] SET Status=@Status, EventTime=SYSUTCDATETIME() WHERE BusinessKey=@BusinessKey; END;",
            "GO",
        ]
    lines += [
        f"CREATE TRIGGER eval.tr_{primary}_audit ON eval.[{primary}] AFTER UPDATE AS BEGIN SET NOCOUNT ON; INSERT eval.audit_history(BusinessKey,Status,Details,CorrelationId) SELECT BusinessKey,'Recorded',CONCAT('status=',Status),CorrelationId FROM inserted; END;",
        "GO",
    ]
    return "\n".join(lines) + "\n"


def seed_sql(domain: str, cfg: dict) -> str:
    lines = ["SET XACT_ABORT ON;", "BEGIN TRANSACTION;"]
    for index, (table, parent) in enumerate(cfg["tables"]):
        parent_column = f", [{ident(parent)}Id]" if parent else ""
        parent_value = ", 1" if parent else ""
        lines.append(
            f"INSERT eval.[{table}] (BusinessKey{parent_column},Status,EventTime,Details,CorrelationId) VALUES ('{domain.upper()}-{index + 1:03d}'{parent_value},'Active',DATEADD(minute,-{index + 1},SYSUTCDATETIME()),'Synthetic baseline record','BASE-{domain.upper()}');"
        )
    for n, entity in enumerate(cfg["entities"], 1):
        lines.append(
            f"INSERT eval.integration_messages(BusinessKey,Status,EventTime,Details,CorrelationId) VALUES ('MSG-{entity}','Processed',DATEADD(hour,-{n},SYSUTCDATETIME()),'Synthetic workflow message','CORR-{entity}');"
        )
    for n in range(1, 4):
        lines.append(
            f"INSERT eval.audit_history(BusinessKey,Status,EventTime,Details,CorrelationId) VALUES ('WF-{domain.upper()}-{n}','Completed',DATEADD(day,-{n},SYSUTCDATETIME()),'Synthetic end-to-end workflow {n}','WF-{domain.upper()}-{n}');"
        )
    if domain == "shipping":
        lines.extend(
            [
                "INSERT eval.shipments(BusinessKey,BookingsId,Status,Details,CorrelationId) VALUES ('SHP-5001',1,'Delivered','Synthetic delivery completed','SHIP-WF-1');",
                "INSERT eval.transport_work_orders(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'EMPTY-SHP-5001',ShipmentsId,'Completed','Empty return work order','SHIP-WF-1' FROM eval.shipments WHERE BusinessKey='SHP-5001';",
                "INSERT eval.shipments(BusinessKey,BookingsId,Status,Details,CorrelationId) VALUES ('SHP-5004',1,'Completed','Import discharge processed','SHIP-WF-4');",
                "INSERT eval.shipment_milestones(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'DISCHARGE-SHP-5004',ShipmentsId,'Completed','Import Discharge','SHIP-WF-4' FROM eval.shipments WHERE BusinessKey='SHP-5004';",
                "INSERT eval.container_assignments(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'CONT-5002',ShipmentsId,'Active','Pilot container assignment','SHIP-WF-2' FROM eval.shipments WHERE BusinessKey='SHP-5001';",
                "INSERT eval.container_events(BusinessKey,ContainerAssignmentsId,Status,Details,CorrelationId) SELECT 'GATE-CONT-5002',ContainerAssignmentsId,'Export Gate In','Terminal accepted event','GATE-CONT-5002' FROM eval.container_assignments WHERE BusinessKey='CONT-5002';",
                "INSERT eval.transport_work_orders(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'WO-5003',ShipmentsId,'Active','MoveType=Empty;SelectedCarrier=CARR-A','SHIP-WF-3' FROM eval.shipments WHERE BusinessKey='SHP-5001';",
                "INSERT eval.carrier_assignments(BusinessKey,TransportWorkOrdersId,Status,Details,CorrelationId) SELECT 'CARR-A-WO-5003',TransportWorkOrdersId,'Active','MoveType=Empty','SHIP-WF-3' FROM eval.transport_work_orders WHERE BusinessKey='WO-5003';",
                "INSERT eval.carrier_assignments(BusinessKey,TransportWorkOrdersId,Status,Details,CorrelationId) SELECT 'CARR-B-WO-5003',TransportWorkOrdersId,'Historical','MoveType=Full','SHIP-WF-3-HISTORY' FROM eval.transport_work_orders WHERE BusinessKey='WO-5003';",
                "INSERT eval.container_assignments(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'CONT-5005',ShipmentsId,'Active','No planned delivery timestamp','SHIP-WF-5' FROM eval.shipments WHERE BusinessKey='SHP-5001';",
            ]
        )
        lifecycle = [
            "Booking",
            "Container Assignment",
            "Empty Release",
            "Empty Gate Out",
            "Stuffing",
            "Export Gate In",
            "Vessel Load",
            "Vessel Departure",
            "Transshipment",
            "Import Discharge",
            "Import Gate Out",
            "Delivery",
            "Empty Return Instruction",
            "Empty Gate In",
            "Inspection",
            "Reusable Status",
        ]
        for position, status in enumerate(lifecycle, 1):
            lines.append(
                "INSERT eval.container_events(BusinessKey,ContainerAssignmentsId,Status,"
                "EventTime,Details,CorrelationId) VALUES "
                f"('LIFE-{position:02d}',1,'{status}',DATEADD(hour,-{20 - position},"
                "SYSUTCDATETIME()),'Synthetic container lifecycle','LIFE-CONT-001');"
            )
    lines += ["COMMIT;", "GO"]
    return "\n".join(lines) + "\n"


def validation_sql(domain: str, cfg: dict) -> str:
    counts = " UNION ALL ".join(
        f"SELECT '{t}' ObjectName, COUNT_BIG(*) RowCount FROM eval.[{t}]"
        for t, _ in cfg["tables"][:3]
    )
    return f"SET NOCOUNT ON;\nIF EXISTS ({counts.replace(' UNION ALL ', ' UNION ALL ')} ) BEGIN SELECT * FROM ({counts}) q; END;\nIF (SELECT COUNT(*) FROM eval.integration_messages) < 5 THROW 51000, 'Baseline workflows missing', 1;\nSELECT 'baseline_valid' ValidationStatus;\nGO\n"


def scenario_sql(domain: str, cfg: dict, index: int) -> tuple[str, str, str, str]:
    entity = cfg["entities"][index - 1]
    marker = f"EVAL-{domain.upper()}-{index:03d}"
    target = cfg["tables"][min(index + 2, len(cfg["tables"]) - 1)][0]
    if domain == "shipping" and index == 1:
        inject = f"DELETE FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001'; INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('{marker}','Open','Downstream empty-return creation absent','{marker}');"
        condition = f"EXISTS (SELECT 1 FROM eval.shipments WHERE BusinessKey='SHP-5001' AND Status='Delivered') AND NOT EXISTS (SELECT 1 FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001') AND EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='{marker}')"
        cleanup = f"DELETE FROM eval.exceptions WHERE CorrelationId='{marker}'; INSERT eval.transport_work_orders(BusinessKey,ShipmentsId,Status,Details,CorrelationId) SELECT 'EMPTY-SHP-5001',ShipmentsId,'Completed','Empty return work order','SHIP-WF-1' FROM eval.shipments WHERE BusinessKey='SHP-5001' AND NOT EXISTS (SELECT 1 FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001');"
    elif domain == "shipping" and index == 2:
        inject = f"DROP INDEX UX_container_events_BusinessKey ON eval.container_events; INSERT eval.container_events(BusinessKey,ContainerAssignmentsId,Status,Details,CorrelationId) SELECT BusinessKey,ContainerAssignmentsId,Status,'Terminal retry copy','{marker}' FROM eval.container_events WHERE BusinessKey='GATE-CONT-5002';"
        condition = f"(SELECT COUNT(*) FROM eval.container_events WHERE BusinessKey='GATE-CONT-5002')=2 AND (SELECT COUNT(*) FROM eval.container_events WHERE CorrelationId='{marker}')=1"
        cleanup = f"DELETE FROM eval.container_events WHERE CorrelationId='{marker}'; CREATE UNIQUE INDEX UX_container_events_BusinessKey ON eval.container_events(BusinessKey);"
    elif domain == "shipping" and index == 3:
        inject = f"UPDATE eval.transport_work_orders SET Details='MoveType=Empty;SelectedCarrier=CARR-B',CorrelationId='{marker}' WHERE BusinessKey='WO-5003';"
        condition = f"EXISTS (SELECT 1 FROM eval.transport_work_orders w JOIN eval.carrier_assignments c ON c.TransportWorkOrdersId=w.TransportWorkOrdersId WHERE w.BusinessKey='WO-5003' AND w.Details LIKE '%CARR-B%' AND c.BusinessKey='CARR-B-WO-5003' AND c.Status='Historical' AND w.CorrelationId='{marker}')"
        cleanup = f"UPDATE eval.transport_work_orders SET Details='MoveType=Empty;SelectedCarrier=CARR-A',CorrelationId='SHIP-WF-3' WHERE BusinessKey='WO-5003' AND CorrelationId='{marker}';"
    elif domain == "shipping" and index == 4:
        inject = f"UPDATE eval.shipments SET Status='In Transit',CorrelationId='{marker}' WHERE BusinessKey='SHP-5004'; INSERT eval.integration_messages(BusinessKey,Status,Details,CorrelationId) VALUES ('DISCHARGE-FAIL-SHP-5004','Failed','Discharge status update failed','{marker}');"
        condition = f"EXISTS (SELECT 1 FROM eval.shipments WHERE BusinessKey='SHP-5004' AND Status='In Transit' AND CorrelationId='{marker}') AND EXISTS (SELECT 1 FROM eval.shipment_milestones WHERE BusinessKey='DISCHARGE-SHP-5004' AND Status='Completed') AND EXISTS (SELECT 1 FROM eval.integration_messages WHERE CorrelationId='{marker}' AND Status='Failed')"
        cleanup = f"DELETE FROM eval.integration_messages WHERE CorrelationId='{marker}'; UPDATE eval.shipments SET Status='Completed',CorrelationId='SHIP-WF-4' WHERE BusinessKey='SHP-5004';"
    elif domain == "shipping" and index == 5:
        inject = f"UPDATE eval.container_assignments SET Details='Actual events present; planned SLA timestamp unavailable',CorrelationId='{marker}' WHERE BusinessKey='CONT-5005';"
        condition = f"EXISTS (SELECT 1 FROM eval.container_assignments WHERE BusinessKey='CONT-5005' AND Details LIKE '%planned SLA timestamp unavailable%' AND CorrelationId='{marker}')"
        cleanup = f"UPDATE eval.container_assignments SET Details='No planned delivery timestamp',CorrelationId='SHIP-WF-5' WHERE BusinessKey='CONT-5005' AND CorrelationId='{marker}';"
    else:
        inject = f"INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES ('{marker}','Open','Synthetic pilot defect for {entity}','{marker}'); UPDATE eval.[{target}] SET Status='Exception',Details='{marker}' WHERE [{ident(target)}Id]=1;"
        condition = f"EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='{marker}' AND Status='Open') AND EXISTS (SELECT 1 FROM eval.[{target}] WHERE Details='{marker}')"
        cleanup = f"DELETE FROM eval.exceptions WHERE CorrelationId='{marker}'; UPDATE eval.[{target}] SET Status='Active',Details='Synthetic baseline record' WHERE Details='{marker}';"
    verify = f"IF NOT ({condition}) THROW 51001, 'Scenario defect not reproducible', 1; SELECT '{entity}' ExpectedEntity, '{marker}' EvidenceValue; GO"
    precondition = f"IF EXISTS (SELECT 1 FROM eval.exceptions WHERE CorrelationId='{marker}') THROW 51002, 'Scenario contaminated before injection', 1; SELECT 'precondition_valid' ValidationStatus; GO"
    return inject + "\nGO\n", precondition + "\n", verify + "\n", cleanup + "\nGO\n"


def manifest(domain: str, cfg: dict) -> list[dict]:
    scenarios = []
    for index, (entity, question) in enumerate(zip(cfg["entities"], cfg["questions"], strict=False), 1):
        scenario_id = f"{domain}-pilot-{index:03d}"
        folder = f"evaluation_scenarios/{domain}/{scenario_id}"
        expected_tables = [
            "exceptions",
            "integration_messages",
            cfg["tables"][min(index + 2, len(cfg["tables"]) - 1)][0],
        ]
        evidence_values = [
            f"EVAL-{domain.upper()}-{index:03d}",
            entity,
            "Exception" if index < 5 else "absence of conclusive timestamps",
        ]
        if domain == "shipping":
            expected_tables = [
                ["shipments", "transport_work_orders", "exceptions"],
                ["container_events", "container_assignments", "integration_messages"],
                ["transport_work_orders", "carrier_assignments", "audit_history"],
                ["shipments", "shipment_milestones", "integration_messages"],
                ["container_assignments", "container_events", "shipment_milestones"],
            ][index - 1]
            evidence_values = [
                [f"EVAL-SHIPPING-{index:03d}", entity, "Delivered", "missing EMPTY-SHP-5001"],
                [f"EVAL-SHIPPING-{index:03d}", entity, "GATE-CONT-5002 count=2"],
                [f"EVAL-SHIPPING-{index:03d}", entity, "Historical", "MoveType=Empty"],
                [f"EVAL-SHIPPING-{index:03d}", entity, "Import Discharge", "Failed"],
                [f"EVAL-SHIPPING-{index:03d}", entity, "planned SLA timestamp unavailable"],
            ][index - 1]
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "domain": domain,
                "database_engine": "sqlserver",
                "database_version": "Azure SQL Database / SQL Server 2022",
                "category": "evidence_safety" if index == 5 else "root_cause",
                "subcategory": [
                    "missing_workflow_output",
                    "duplicate_integration",
                    "incorrect_selection",
                    "stalled_status",
                    "insufficient_evidence",
                ][index - 1],
                "difficulty": ["medium", "hard", "hard", "medium", "hard"][index - 1],
                "question": question,
                "baseline_script": f"evaluation_databases/{domain}/sql/02_seed.sql",
                "setup_script": f"{folder}/inject.sql",
                "verification_script": f"{folder}/verify.sql",
                "cleanup_script": f"{folder}/cleanup.sql",
                "expected_response_type": RESPONSE_TYPES[index - 1],
                "expected_entities": [entity],
                "expected_root_cause_concepts": [ROOT_CAUSES[index - 1]] if index < 5 else [],
            "expected_tables": expected_tables,
                "expected_columns": ["BusinessKey", "Status", "CorrelationId", "Details"],
                "expected_database_objects": [f"eval.vw_{domain}_operations_1"],
                "expected_procedures": [f"eval.usp_{domain}_workflow_{index}"],
                "expected_functions": [f"eval.fn_{domain}_active_status"],
                "expected_triggers": [f"eval.tr_{cfg['tables'][1][0]}_audit"],
                "expected_jobs": [],
            "required_evidence": evidence_values,
                "acceptable_fix_concepts": [
                    "transactional workflow completion",
                    "idempotency key",
                    "active assignment filtering",
                    "retry and reconciliation",
                    "collect additional timestamp evidence",
                ][index - 1 : index],
                "prohibited_claims": [
                    "objects or evidence not returned by the database",
                    "production impact inferred from synthetic data",
                ],
                "critical_failure_rules": [
                    "fabricated_evidence",
                    "invented_database_object",
                    "confirmed_root_cause_without_supporting_evidence",
                ],
                "scenario_version": 1,
                "active": True,
            }
        )
    return scenarios


def docs(domain: str, cfg: dict) -> str:
    relationships = "\n".join(
        f"- `eval.{table}`" + (f" → `eval.{parent}`" if parent else " (root)")
        for table, parent in cfg["tables"]
    )
    return f"# {cfg['title']} synthetic evaluation database\n\nAzure SQL-compatible, synthetic-only pilot database. No production-derived data is included.\n\n## Workflows\n\n1. Intake/master-data → operational transaction → completion.\n2. External integration message → processing → audit/exception handling.\n3. Batch processing → downstream record → reconciliation.\n\n## Relationships\n\n{relationships}\n\n## Objects\n\n{len(cfg['tables'])} tables, 5 views, 8 stored procedures, one scalar function, one audit trigger, realistic PK/FK and status/time indexes.\n"


def reset_sql(domain: str, cfg: dict) -> str:
    deletes = "\n".join(f"DELETE FROM eval.[{table}];" for table, _ in reversed(cfg["tables"]))
    reseeds = "\n".join(
        f"DBCC CHECKIDENT ('eval.{table}', RESEED, 0);" for table, _ in cfg["tables"]
    )
    return f"SET XACT_ABORT ON;\nBEGIN TRANSACTION;\n{deletes}\n{reseeds}\nCOMMIT;\nGO\n:r 02_seed.sql\n"


def destroy_sql(domain: str, cfg: dict) -> str:
    drops = []
    for n in range(1, 9):
        drops.append(f"DROP PROCEDURE IF EXISTS eval.usp_{domain}_workflow_{n};")
    for n in range(1, 6):
        drops.append(f"DROP VIEW IF EXISTS eval.vw_{domain}_operations_{n};")
    drops.append(f"DROP FUNCTION IF EXISTS eval.fn_{domain}_active_status;")
    drops.extend(f"DROP TABLE IF EXISTS eval.[{table}];" for table, _ in reversed(cfg["tables"]))
    drops.append("DROP TABLE IF EXISTS eval.evaluation_marker;")
    drops.append("IF SCHEMA_ID('eval') IS NOT NULL EXEC('DROP SCHEMA eval');")
    return "\n".join(drops) + "\nGO\n"


def main() -> None:
    for domain, cfg in DOMAINS.items():
        db = ROOT / "evaluation_databases" / domain
        sql = db / "sql"
        sql.mkdir(parents=True, exist_ok=True)
        (sql / "01_create.sql").write_text(create_sql(domain, cfg), encoding="utf-8")
        (sql / "02_seed.sql").write_text(seed_sql(domain, cfg), encoding="utf-8")
        (sql / "03_validate.sql").write_text(validation_sql(domain, cfg), encoding="utf-8")
        (sql / "04_reset.sql").write_text(reset_sql(domain, cfg), encoding="utf-8")
        (sql / "05_destroy.sql").write_text(destroy_sql(domain, cfg), encoding="utf-8")
        (db / "README.md").write_text(docs(domain, cfg), encoding="utf-8")
        scenarios = manifest(domain, cfg)
        scenario_root = ROOT / "evaluation_scenarios" / domain
        (scenario_root / "scenarios.json").write_text(
            json.dumps(scenarios, indent=2) + "\n", encoding="utf-8"
        )
        for index, scenario in enumerate(scenarios, 1):
            folder = scenario_root / scenario["scenario_id"]
            folder.mkdir(parents=True, exist_ok=True)
            inject, precondition, verify, cleanup = scenario_sql(domain, cfg, index)
            (folder / "scenario.json").write_text(
                json.dumps(scenario, indent=2) + "\n", encoding="utf-8"
            )
            (folder / "baseline_reset.sql").write_text(
                f":r ../../../evaluation_databases/{domain}/sql/04_reset.sql\n", encoding="utf-8"
            )
            (folder / "inject.sql").write_text(inject, encoding="utf-8")
            (folder / "precondition.sql").write_text(precondition, encoding="utf-8")
            (folder / "verify.sql").write_text(verify, encoding="utf-8")
            (folder / "cleanup.sql").write_text(cleanup, encoding="utf-8")


if __name__ == "__main__":
    main()

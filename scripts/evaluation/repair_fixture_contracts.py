from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ("banking", "orders", "shipping", "payroll", "clinic")
DATABASES = {domain: f"Eval{domain.title()}" for domain in DOMAINS}

PILOT_ENTITIES = {
    "banking": [
        ("TRF-3101", "transfer", "transfers"),
        ("PMT-3102", "payment_instruction", "payment_instructions"),
        ("ACC-3103", "account", "accounts"),
        ("BAT-3104", "settlement_batch", "batch_runs"),
        ("TXN-3105", "transaction", "transactions"),
    ],
    "orders": [
        ("ORD-7101", "order", "sales_orders"),
        ("ORD-7102", "order", "sales_orders"),
        ("SKU-8103", "sku", "products"),
        ("PICK-9104", "pick_task", "pick_tasks"),
        ("PO-1205", "purchase_order", "purchase_orders"),
    ],
    "payroll": [
        ("EMP-1042", "employee", "employees"),
        ("PAY-7003", "payment", "payments"),
        ("TIME-8821", "time_entry", "time_entries"),
        ("RUN-2026-07-A", "payroll_run", "payroll_runs"),
        ("TAX-2026-07", "tax_filing", "tax_filings"),
    ],
    "clinic": [
        ("APT-2101", "appointment", "appointments"),
        ("CLM-3302", "claim", "claims"),
        ("LAB-4403", "lab_result", "lab_results"),
        ("ENC-5504", "encounter", "encounters"),
        ("PAT-6605", "patient", "patients"),
    ],
    "shipping": [
        ("SHP-5001", "shipment", "shipments"),
        ("CONT-5002", "container_assignment", "container_assignments"),
        ("WO-5003", "transport_work_order", "transport_work_orders"),
        ("SHP-5004", "shipment", "shipments"),
        ("CONT-5005", "container_assignment", "container_assignments"),
    ],
}

SHIPPING_DEFECT_TABLES = ["exceptions", "container_events", "transport_work_orders", "shipments", "container_assignments"]
SHIPPING_LINK_COLUMNS = [
    ("BusinessKey", "CorrelationId"),
    ("ContainerAssignmentsId", "ContainerAssignmentsId"),
    ("TransportWorkOrdersId", "TransportWorkOrdersId"),
    ("ShipmentsId", "ShipmentsId"),
    ("ContainerAssignmentsId", "ContainerAssignmentsId"),
]


def _baseline_key(domain: str, table: str) -> str:
    seed = (ROOT / f"evaluation_databases/{domain}/sql/02_seed.sql").read_text(encoding="utf-8")
    match = re.search(
        rf"INSERT\s+eval\.\[?{re.escape(table)}\]?\s*\([^;]+?VALUES\s*\(N?'([^']+)'",
        seed,
        re.I | re.S,
    )
    if not match:
        raise RuntimeError(f"Cannot find baseline business key for {domain}.{table}")
    return match.group(1)


def _repair_nonshipping_pilot(domain: str, index: int, value: str, table: str) -> None:
    root = ROOT / f"evaluation_scenarios/{domain}/{domain}-pilot-{index:03d}"
    correlation = f"EVAL-{domain.upper()}-{index:03d}"
    base = _baseline_key(domain, table)
    setup = (
        "SET XACT_ABORT ON;\nBEGIN TRANSACTION;\n"
        f"UPDATE eval.[{table}] SET BusinessKey=N'{value}',Status=N'Exception',Details=N'{correlation}',CorrelationId=N'{correlation}' WHERE BusinessKey=N'{base}';\n"
        f"IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;\n"
        f"INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'{correlation}',N'Open',N'Synthetic pilot defect for {value}',N'{correlation}');\n"
        "COMMIT;\nGO\n"
    )
    verify = (
        "SET NOCOUNT ON;\n"
        f"IF (SELECT COUNT(*) FROM eval.[{table}] WHERE BusinessKey=N'{value}') <> 1 THROW 51021, 'Exact expected entity missing or duplicated', 1;\n"
        f"IF NOT EXISTS (SELECT 1 FROM eval.[{table}] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.BusinessKey=N'{value}' AND e.CorrelationId=N'{correlation}' AND d.Status=N'Open') THROW 51022, 'Defect is not linked to expected entity', 1;\n"
        f"SELECT N'ENTITY_FOUND' EntityStatus,N'eval.{table}' EntityTable,N'BusinessKey' EntityColumn,N'{value}' ExpectedEntity,COUNT(*) ExactRowCount FROM eval.[{table}] WHERE BusinessKey=N'{value}';\nGO\n"
    )
    cleanup = (
        "SET XACT_ABORT ON;\nBEGIN TRANSACTION;\n"
        f"DELETE FROM eval.exceptions WHERE CorrelationId=N'{correlation}';\n"
        f"UPDATE eval.[{table}] SET BusinessKey=N'{base}',Status=N'Active',Details=N'Synthetic baseline record',CorrelationId=N'BASE-{domain.upper()}' WHERE BusinessKey=N'{value}' AND CorrelationId=N'{correlation}';\n"
        "COMMIT;\nGO\n"
    )
    (root / "inject.sql").write_text(setup, encoding="utf-8", newline="\n")
    (root / "verify.sql").write_text(verify, encoding="utf-8", newline="\n")
    (root / "cleanup.sql").write_text(cleanup, encoding="utf-8", newline="\n")


def _metadata(item: dict, domain: str) -> dict:
    scenario_id = item["scenario_id"]
    if "-pilot-" in scenario_id:
        index = int(scenario_id.rsplit("-", 1)[1])
        value, entity_type, table = PILOT_ENTITIES[domain][index - 1]
        item["expected_entities"] = [value]
        item["expected_entity_type"] = entity_type
        defect_table = SHIPPING_DEFECT_TABLES[index - 1] if domain == "shipping" else "exceptions"
        defect_value = f"EVAL-{domain.upper()}-{index:03d}"
        defect_column = "BusinessKey" if domain == "shipping" and index == 1 else "CorrelationId"
        entity_link_column, defect_link_column = (SHIPPING_LINK_COLUMNS[index - 1] if domain == "shipping" else ("CorrelationId", "CorrelationId"))
        if table not in item.get("expected_tables", []):
            item.setdefault("expected_tables", []).append(table)
        evidence = item.get("required_evidence", [])
        if evidence:
            # Replace stale shifted pilot identifiers while preserving concepts/correlation.
            entity_like = re.compile(r"^[A-Z]+(?:-[A-Z0-9]+){1,4}$")
            replaced = False
            for offset, existing in enumerate(evidence):
                if entity_like.fullmatch(str(existing)) and not str(existing).startswith("EVAL-"):
                    evidence[offset] = value
                    replaced = True
                    break
            if not replaced:
                evidence.append(value)
    else:
        declared_value = item["expected_entities"][0]
        question_value = declared_value.rsplit("-", 1)[0] if item.get("category") == "partial_entity_resolution" else declared_value
        value = f"{declared_value}-A" if item.get("category") == "ambiguous_entity_resolution" else declared_value
        entity_type = item.get("category", "business_entity")
        table = item["expected_tables"][0]
        defect_table = "exceptions"
        defect_value = next((x for x in item.get("required_evidence", []) if str(x).startswith("EVAL-")), "")
        defect_column = "CorrelationId"
        entity_link_column, defect_link_column = "CorrelationId", "CorrelationId"
    item.update({
        "expected_entity_value": value,
        "expected_entity_question_value": question_value if "-benchmark-" in scenario_id else value,
        "expected_entity_type": entity_type,
        "expected_entity_schema": "eval",
        "expected_entity_table": table,
        "expected_entity_column": "BusinessKey",
        "expected_entity_match_mode": "partial_ambiguous" if item.get("category") == "ambiguous_entity_resolution" else "exact",
        "expected_entity_database": DATABASES[domain],
        "expected_defect_table": defect_table,
        "expected_defect_column": defect_column,
        "expected_defect_value": defect_value,
        "expected_entity_link_column": entity_link_column,
        "expected_defect_link_column": defect_link_column,
    })
    return item


def main() -> None:
    for domain in DOMAINS:
        if domain != "shipping":
            for index, (value, _entity_type, table) in enumerate(PILOT_ENTITIES[domain], 1):
                _repair_nonshipping_pilot(domain, index, value, table)
        manifest = ROOT / f"evaluation_scenarios/{domain}/scenarios.json"
        items = json.loads(manifest.read_text(encoding="utf-8"))
        repaired = [_metadata(item, domain) for item in items]
        manifest.write_text(json.dumps(repaired, indent=2) + "\n", encoding="utf-8", newline="\n")
        for item in repaired:
            path = ROOT / f"evaluation_scenarios/{domain}/{item['scenario_id']}/scenario.json"
            path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")
            if "-benchmark-" in item["scenario_id"]:
                value = item["expected_entity_value"]
                table = item["expected_entity_table"]
                correlation = item["expected_defect_value"]
                verify = ROOT / item["verification_script"]
                if item["expected_entity_match_mode"] == "partial_ambiguous":
                    predicate = f"BusinessKey LIKE N'{item['expected_entity_question_value']}%'"
                    invalid_condition = "< 2"
                else:
                    predicate = f"BusinessKey=N'{value}'"
                    invalid_condition = "<> 1"
                verify.write_text(
                    "SET NOCOUNT ON;\n"
                    f"IF (SELECT COUNT(*) FROM eval.[{table}] e JOIN eval.exceptions d ON d.CorrelationId=e.CorrelationId WHERE e.{predicate} AND e.CorrelationId=N'{correlation}') {invalid_condition} THROW 51100, 'Benchmark entity/defect fixture invalid', 1;\n"
                    f"SELECT N'verified' verification_status,BusinessKey,Status,CorrelationId FROM eval.[{table}] WHERE {predicate} AND CorrelationId=N'{correlation}';\nGO\n",
                    encoding="utf-8", newline="\n"
                )


if __name__ == "__main__":
    main()

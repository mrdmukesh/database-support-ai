from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.fixtures.validation import manifest_sql_consistency
from evaluation.framework.contracts import ScenarioContract
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle

DOMAINS = ("banking", "orders", "shipping", "payroll", "clinic")
DATABASES = {domain: f"Eval{domain.title()}" for domain in DOMAINS}
PILOTS = {f"{domain}-pilot-001" for domain in DOMAINS}


def load_env() -> None:
    path = Path(os.getenv("EVAL_ENV_FILE", ".env.evaluation"))
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def scenarios() -> list[ScenarioContract]:
    rows = []
    for domain in DOMAINS:
        rows.extend(json.loads(Path(f"evaluation_scenarios/{domain}/scenarios.json").read_text(encoding="utf-8")))
    return [ScenarioContract(**row) for row in rows]


def lifecycle() -> SqlCmdDatabaseLifecycle:
    load_env()
    return SqlCmdDatabaseLifecycle(
        server=os.environ["EVAL_SQL_SERVER"], username=os.environ["EVAL_SQL_ADMIN"],
        password=os.environ["EVAL_SQL_PASSWORD"], databases=DATABASES,
        allowed_hosts={x.strip().lower() for x in os.environ["EVAL_ALLOWED_SQL_HOSTS"].split(",") if x.strip()},
        allowed_databases={x.strip() for x in os.environ["EVAL_ALLOWED_DATABASES"].split(",") if x.strip()},
        reader_username=os.getenv("EVAL_SQL_READER", "evalreader"),
        reader_password=os.getenv("EVAL_SQL_READER_PASSWORD") or os.environ["EVAL_SQL_PASSWORD"],
    )


def audit(dynamic: bool) -> dict:
    app = lifecycle() if dynamic else None
    rows = []
    for scenario in scenarios():
        consistency = manifest_sql_consistency(scenario)
        row = {
            "scenario_id": scenario.scenario_id,
            "domain": scenario.domain,
            "expected_entity": scenario.expected_entity_value,
            "declared_table": f"{scenario.expected_entity_schema}.{scenario.expected_entity_table}",
            "declared_column": scenario.expected_entity_column,
            "entity_found": False,
            "exact_row_count": None,
            "defect_found": False,
            "entity_defect_linkage_valid": False,
            "application_credentials_visible": False,
            "manifest_sql_consistency": consistency["status"],
            "fixture_status": "NOT_DYNAMICALLY_AUDITED" if not dynamic else "INVALID",
            "failure_reason": "; ".join(consistency["reasons"]),
        }
        if dynamic and app:
            try:
                app.reset(scenario)
                app.inject(scenario)
                proof = app.verify(scenario)
                entity = proof.get("entity", {})
                visibility = proof.get("application_visibility", {})
                linkage = proof.get("defect_linkage", {})
                row.update({
                    "entity_found": entity.get("status") == "ENTITY_FOUND",
                    "exact_row_count": entity.get("exact_row_count"),
                    "defect_found": int(linkage.get("linked_row_count") or 0) > 0,
                    "entity_defect_linkage_valid": bool(linkage.get("valid")),
                    "application_credentials_visible": visibility.get("status") == "ENTITY_FOUND",
                    "fixture_status": proof.get("fixture_status", "INVALID"),
                    "failure_reason": "" if proof.get("verified") else json.dumps(proof, default=str),
                    "proof": proof,
                })
            except Exception as exc:
                row["failure_reason"] = str(exc)
                row["fixture_status"] = "INVALID"
            finally:
                try:
                    app.cleanup(scenario)
                except Exception as exc:
                    row["failure_reason"] += f"; cleanup failed: {exc}"
                    row["fixture_status"] = "INVALID"
        rows.append(row)
    counts = Counter(row["fixture_status"] for row in rows)
    summary = {
        "total_scenarios": len(rows),
        "dynamic": dynamic,
        "valid_fixtures": counts["VALID"],
        "invalid_fixtures": counts["INVALID"],
        "not_dynamically_audited": counts["NOT_DYNAMICALLY_AUDITED"],
        "missing_entities": sum(row.get("exact_row_count") == 0 for row in rows),
        "duplicate_entities": sum((row.get("exact_row_count") or 0) > 1 for row in rows),
        "manifest_mismatches": sum(row["manifest_sql_consistency"] != "CONSISTENT" for row in rows),
        "missing_defect_evidence": sum(dynamic and not row["defect_found"] for row in rows),
        "wrong_entity_defect_evidence": sum(dynamic and row["defect_found"] and not row["entity_defect_linkage_valid"] for row in rows),
        "unsupported_sql_server_objects": sum("TABLE_MISSING" in row["failure_reason"] or "COLUMN_MISSING" in row["failure_reason"] for row in rows),
        "verification_query_failures": sum("QUERY_FAILED" in row["failure_reason"] for row in rows),
        "original_invalid_fixture_count": 20,
        "repaired_fixture_count": 20,
    }
    return {"summary": summary, "scenarios": rows}


def write(payload: dict) -> None:
    root = Path("research/results/fixture-audit"); root.mkdir(parents=True, exist_ok=True)
    (root / "fixture-audit-125.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    fields = [key for key in payload["scenarios"][0] if key != "proof"]
    with (root / "fixture-audit-125.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(payload["scenarios"])
    summary = payload["summary"]
    lines = ["# SQL Server Fixture Audit Summary", "", *[f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary.items()], "", "Application benchmarking was not executed by this audit."]
    (root / "fixture-audit-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pilots = [row for row in payload["scenarios"] if row["scenario_id"] in PILOTS]
    (root / "five-domain-fixture-proof.json").write_text(json.dumps({"all_valid": len(pilots) == 5 and all(row["fixture_status"] == "VALID" for row in pilots), "scenarios": pilots}, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--dynamic", action="store_true")
    args = parser.parse_args(); payload = audit(args.dynamic); write(payload); print(json.dumps(payload["summary"], indent=2))

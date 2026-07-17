from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.cli.__main__ import all_scenarios, required_env
from evaluation.preflight import DATABASES
from evaluation.runners.mysql_database import MySQLDatabaseLifecycle


def main(scenario_id: str, output: Path) -> None:
    scenario = next(item for item in all_scenarios() if item.scenario_id == scenario_id)
    lifecycle = MySQLDatabaseLifecycle(
        host=required_env("EVAL_MYSQL_HOST"), port=int(os.getenv("EVAL_MYSQL_PORT", "3306")),
        username=required_env("EVAL_MYSQL_USER"), password=required_env("EVAL_MYSQL_PASSWORD"),
        databases=DATABASES,
        allowed_hosts={x.strip().lower() for x in required_env("EVAL_ALLOWED_MYSQL_HOSTS").split(",") if x.strip()},
        allowed_databases={x.strip() for x in required_env("EVAL_ALLOWED_DATABASES").split(",") if x.strip()},
    )
    result = {
        "scenario_id": scenario.scenario_id, "verified_at": datetime.now(timezone.utc).isoformat(),
        "supported_database_engine": scenario.database_engine, "actual_database_engine": "mysql",
        "translation_status": "bounded_tsql_translation", "fixture_validity": "VERIFICATION_FAILED",
        "question": scenario.question, "expected_entities": scenario.expected_entities,
        "required_evidence": scenario.required_evidence, "expected_tables": scenario.expected_tables,
        "expected_procedures": scenario.expected_procedures, "expected_functions": scenario.expected_functions,
        "expected_triggers": scenario.expected_triggers, "records": {},
    }
    lifecycle.reset(scenario)
    try:
        lifecycle.inject(scenario)
        result["verification"] = lifecycle.verify(scenario)
        needles = [*scenario.expected_entities, *scenario.required_evidence]
        with lifecycle._connect(scenario.domain) as connection, connection.cursor() as cursor:
            for table in scenario.expected_tables:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME IN ('BusinessKey','Status','CorrelationId','Details')",
                    (table,),
                )
                columns = [row[0] for row in cursor.fetchall()]
                if not columns:
                    result["records"][table] = []
                    continue
                clauses = " OR ".join(f"CAST(`{column}` AS CHAR)=%s" for column in columns for _ in needles)
                params = [needle for _column in columns for needle in needles]
                cursor.execute(f"SELECT * FROM `{table}` WHERE {clauses} LIMIT 20", params)
                names = [item[0] for item in cursor.description]
                result["records"][table] = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        result["fixture_validity"] = "VALID"
    finally:
        lifecycle.cleanup(scenario)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"scenario_id": scenario_id, "fixture_validity": result["fixture_validity"], "output": str(output)}))


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))

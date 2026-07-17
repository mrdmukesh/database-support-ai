from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.cli.__main__ import all_scenarios, required_env
from evaluation.preflight import DATABASES
from evaluation.runners.mysql_database import MySQLDatabaseLifecycle


def main() -> None:
    lifecycle = MySQLDatabaseLifecycle(
        host=required_env("EVAL_MYSQL_HOST"),
        port=int(os.getenv("EVAL_MYSQL_PORT", "3306")),
        username=required_env("EVAL_MYSQL_USER"),
        password=required_env("EVAL_MYSQL_PASSWORD"),
        databases=DATABASES,
        allowed_hosts={item.strip().lower() for item in required_env("EVAL_ALLOWED_MYSQL_HOSTS").split(",") if item.strip()},
        allowed_databases={item.strip() for item in required_env("EVAL_ALLOWED_DATABASES").split(",") if item.strip()},
    )
    scenarios = all_scenarios()
    for index, scenario in enumerate(scenarios, 1):
        print(json.dumps({"index": index, "total": len(scenarios), "scenario_id": scenario.scenario_id, "stage": "fixture_validation_started"}), flush=True)
        lifecycle.reset(scenario)
        try:
            lifecycle.inject(scenario)
            lifecycle.verify(scenario)
        finally:
            lifecycle.cleanup(scenario)
        print(json.dumps({"index": index, "total": len(scenarios), "scenario_id": scenario.scenario_id, "stage": "fixture_validation_passed"}), flush=True)


if __name__ == "__main__":
    main()

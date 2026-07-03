from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.db.connector import DatabaseConnector
from legacydb_copilot.services.benchmark_runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run demo-only Database Support AI benchmarks.")
    parser.add_argument("--engine", default="mysql", choices=[engine.value for engine in DatabaseEngine])
    parser.add_argument("--connection-string", required=True)
    parser.add_argument(
        "--allow-customer-db",
        action="store_true",
        help="Dangerous override for internal test automation only. By default only demo/test/benchmark databases are allowed.",
    )
    args = parser.parse_args()

    connector = DatabaseConnector(DatabaseEngine(args.engine), args.connection_string)
    connector.connect()
    try:
        result = run_benchmark(
            connector,
            connection_string=args.connection_string,
            allow_customer_db=args.allow_customer_db,
        )
        print(json.dumps(asdict(result), indent=2, default=str))
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()

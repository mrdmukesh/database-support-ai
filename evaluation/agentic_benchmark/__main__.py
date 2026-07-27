from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.agentic_benchmark.loader import load_agentic_25
from evaluation.agentic_benchmark.runner import (
    AgenticBenchmarkRunner,
    capture_from_execution,
)


def execute() -> None:
    parser = argparse.ArgumentParser(
        description="Run the protected AG-10 25-scenario agentic benchmark."
    )
    parser.add_argument(
        "--output",
        default="evaluation/results/agentic-25",
        help="Artifact output directory.",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--api-retries", type=int, default=3)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and display the protected manifest without investigations.",
    )
    args = parser.parse_args()
    manifest, ground_truth, scenarios = load_agentic_25()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "scenario_count": len(manifest),
                    "databases": sorted({item.database for item in manifest}),
                    "scenarios": [
                        {
                            "scenario_id": item.scenario_id,
                            "database": item.database,
                            "domain": item.domain,
                            "question": item.question,
                            "ground_truth_status": ground_truth[
                                item.scenario_id
                            ].review_status.value,
                        }
                        for item in manifest
                    ],
                    "ground_truth_isolation": (
                        "Expected answers are loaded by the scorer after investigation."
                    ),
                },
                indent=2,
            )
        )
        return

    # Importing the existing CLI here avoids loading secrets/configuration for dry runs.
    from evaluation.cli.__main__ import build_runner

    runner_args = argparse.Namespace(
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        api_retries=args.api_retries,
        concurrency=1,
    )
    existing = build_runner(runner_args)
    run_name = f"agentic-25-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    run_id = existing.create_run(run_name)

    def investigate(entry):
        execution = existing.run_scenario(run_id, scenarios[entry.scenario_id])
        return capture_from_execution(entry, execution)

    summary = AgenticBenchmarkRunner(
        manifest=manifest,
        ground_truth=ground_truth,
        execute=investigate,
        output_root=Path(args.output) / run_id,
        database_engine=existing.config.database_engine or "sqlserver",
    ).run()
    print(json.dumps({"run_id": run_id, **summary}, indent=2, default=str))


if __name__ == "__main__":
    execute()

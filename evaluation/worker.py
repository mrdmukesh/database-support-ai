from __future__ import annotations

import argparse
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from evaluation.job_executor import InProcessEvaluationExecutor
from legacydb_copilot.config import Settings
from legacydb_copilot.db.session import create_session_factory
from legacydb_copilot.services.evaluation_job_worker import EvaluationJobWorker


def build_worker() -> EvaluationJobWorker:
    return EvaluationJobWorker(
        create_session_factory(Settings.from_env().database_url), InProcessEvaluationExecutor(),
        worker_id=f"{socket.gethostname()}-{os.getpid()}",
        stale_after_seconds=int(os.getenv("EVALUATION_WORKER_STALE_SECONDS", "900")),
    )


def run_worker(*, once: bool = False, poll_seconds: float = 5, stop_event: Event | None = None) -> None:
    worker = build_worker()
    worker.recover_stale_jobs()
    stop_event = stop_event or Event()
    while not stop_event.is_set():
        worked = worker.run_once()
        if once:
            return
        if not worked:
            stop_event.wait(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Durable evaluation job worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("EVALUATION_WORKER_POLL_SECONDS", "5")))
    args = parser.parse_args()
    from legacydb_copilot.runtime_diagnostics import write_runtime_diagnostic
    write_runtime_diagnostic(
        "evaluation-worker",
        Path(os.getenv("EVAL_WORKER_RUNTIME_DIAGNOSTIC", ".tmp/local-evaluation/worker-runtime.json")),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    run_worker(once=args.once, poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()

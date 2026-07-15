from __future__ import annotations

import argparse
import os
import socket
import time

from evaluation.job_executor import InProcessEvaluationExecutor
from legacydb_copilot.config import Settings
from legacydb_copilot.db.session import create_session_factory
from legacydb_copilot.services.evaluation_job_worker import EvaluationJobWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="Durable evaluation job worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("EVALUATION_WORKER_POLL_SECONDS", "5")))
    args = parser.parse_args()
    worker = EvaluationJobWorker(
        create_session_factory(Settings.from_env().database_url), InProcessEvaluationExecutor(),
        worker_id=f"{socket.gethostname()}-{os.getpid()}",
        stale_after_seconds=int(os.getenv("EVALUATION_WORKER_STALE_SECONDS", "900")),
    )
    worker.recover_stale_jobs()
    while True:
        worked = worker.run_once()
        if args.once:
            return
        if not worked:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging
import os
from threading import Event, Thread
from typing import Callable

logger = logging.getLogger(__name__)


def evaluation_worker_enabled() -> bool:
    return os.getenv("EVALUATION_WORKER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


class EvaluationWorkerRuntime:
    """Owns one daemon worker thread for a single application process."""

    def __init__(self, target: Callable[..., None] | None = None):
        self.stop_event = Event()
        self.thread: Thread | None = None
        self.target = target

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        target = self.target or self._run
        self.thread = Thread(
            target=target,
            kwargs={"stop_event": self.stop_event},
            name="evaluation-job-worker",
            daemon=True,
        )
        self.thread.start()
        logger.info("Evaluation job worker started")

    def stop(self, timeout: float = 10) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=timeout)
        logger.info("Evaluation job worker stop requested")

    @staticmethod
    def _run(*, stop_event: Event) -> None:
        from evaluation.worker import run_worker

        run_worker(
            poll_seconds=float(os.getenv("EVALUATION_WORKER_POLL_SECONDS", "5")),
            stop_event=stop_event,
        )

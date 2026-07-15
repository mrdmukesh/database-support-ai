from __future__ import annotations

from threading import Event

from legacydb_copilot.services.evaluation_worker_runtime import EvaluationWorkerRuntime, evaluation_worker_enabled


def test_worker_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EVALUATION_WORKER_ENABLED", raising=False)
    assert evaluation_worker_enabled() is False


def test_worker_enablement_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("EVALUATION_WORKER_ENABLED", "true")
    assert evaluation_worker_enabled() is True


def test_runtime_starts_once_and_stops_gracefully() -> None:
    entered = Event()
    exited = Event()

    def target(*, stop_event: Event) -> None:
        entered.set()
        stop_event.wait(2)
        exited.set()

    runtime = EvaluationWorkerRuntime(target)
    runtime.start()
    first_thread = runtime.thread
    assert entered.wait(1)
    runtime.start()
    assert runtime.thread is first_thread
    runtime.stop(timeout=2)
    assert exited.is_set()
    assert runtime.thread is not None and not runtime.thread.is_alive()

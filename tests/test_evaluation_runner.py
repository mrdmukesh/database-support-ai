from __future__ import annotations

import json
import threading
import time
from dataclasses import replace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evaluation.cli.__main__ import latest_statuses
from evaluation.framework.models import Base, EvaluationScenarioExecutionModel
from evaluation.framework.redaction import redact
from evaluation.framework.scenario_loader import load_scenarios
from evaluation.runners.contracts import RunnerConfig, RunnerContext, TransientAPIError
from evaluation.runners.runner import FAILED_STATUSES, EvaluationRunner
from evaluation.runners.store import SQLAlchemyExecutionStore


def scenario(domain="shipping", scenario_id="shipping-pilot-001"):
    item = load_scenarios(f"evaluation_scenarios/{domain}/scenarios.json")[0]
    return replace(item, scenario_id=scenario_id, domain=domain)


class FakeDatabase:
    def __init__(self, *, verified=True, fail_cleanup=False, delay=0.0):
        self.verified = verified
        self.fail_cleanup = fail_cleanup
        self.delay = delay
        self.calls = []
        self.active = 0
        self.overlap = False
        self.guard = threading.Lock()

    def reset(self, item):
        with self.guard:
            self.active += 1
            self.overlap = self.overlap or self.active > 1
        self.calls.append("reset")
        time.sleep(self.delay)

    def inject(self, item):
        self.calls.append("inject")

    def verify(self, item):
        self.calls.append("verify")
        return {"verified": self.verified}

    def cleanup(self, item):
        self.calls.append("cleanup")
        with self.guard:
            self.active -= 1
        if self.fail_cleanup:
            raise RuntimeError("cleanup password=top-secret")


class FakeAPI:
    def __init__(self, *, submission=None, detail=None, submit_error=None, poll_error=None):
        self.submission = submission or {
            "investigation_id": "INV-1",
            "confidence": 0.8,
            "sources": ["EV-1"],
        }
        self.detail = detail or {
            "id": "INV-1",
            "status": "AI_ANSWERED",
            "ai_answer": "Supported result",
        }
        self.submit_error = submit_error
        self.poll_error = poll_error

    def submit(self, payload):
        if self.submit_error:
            raise self.submit_error
        return self.submission, 201

    def retrieve(self, investigation_id):
        if self.poll_error:
            raise self.poll_error
        return self.detail, 200


class FakeStore:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.records = []

    def create_run(self, *, run_name, metadata):
        return "RUN-1"

    def persist(self, run_id, item, result):
        if self.fail:
            raise RuntimeError("database_url=postgres://user:secret@host/db")
        self.records.append(result)

    def next_attempt(self, run_id, scenario_id):
        return sum(1 for item in self.records if item.scenario_id == scenario_id) + 1

    def statuses(self, run_id):
        return []


def config(tmp_path, **overrides):
    values = {
        "api_base_url": "http://test",
        "access_token": "secret-token",
        "context": RunnerContext(
            "ORG",
            "WS",
            "USER",
            {
                domain: f"CONN-{domain}"
                for domain in ("payroll", "clinic", "orders", "banking", "shipping")
            },
        ),
        "poll_interval_seconds": 0,
        "retry_backoff_seconds": 0,
        "recovery_root": tmp_path,
    }
    values.update(overrides)
    return RunnerConfig(**values)


def runner(tmp_path, *, database=None, api=None, store=None, clock=time.monotonic):
    return EvaluationRunner(
        config=config(tmp_path),
        database=database or FakeDatabase(),
        api=api or FakeAPI(),
        store=store or FakeStore(),
        sleeper=lambda _seconds: None,
        clock=clock,
    )


def test_successful_scenario_execution(tmp_path):
    store = FakeStore()
    result = runner(tmp_path, store=store).run_scenario("RUN", scenario())
    assert result.status == "completed"
    assert result.investigation_id == "INV-1"
    assert result.extracted_result["evidence"] == []
    assert len(store.records) == 1


def test_setup_failure_stops_before_api_and_cleans_up(tmp_path):
    database = FakeDatabase(verified=False)
    api = FakeAPI(submit_error=AssertionError("must not submit"))
    result = runner(tmp_path, database=database, api=api).run_scenario("RUN", scenario())
    assert result.status == "setup_failed"
    assert database.calls == ["reset", "inject", "verify", "cleanup"]


def test_api_submission_failure(tmp_path):
    result = runner(tmp_path, api=FakeAPI(submit_error=RuntimeError("bad request"))).run_scenario(
        "RUN", scenario()
    )
    assert result.status == "api_submission_failed"


def test_timeout(tmp_path):
    tick = [-0.5]

    def clock():
        tick[0] += 0.5
        return tick[0]

    app = runner(tmp_path, api=FakeAPI(detail={"status": "OPEN"}), clock=clock)
    app.config = replace(app.config, timeout_seconds=1)
    assert app.run_scenario("RUN", scenario()).status == "timeout"


def test_polling_failure(tmp_path):
    result = runner(
        tmp_path, api=FakeAPI(poll_error=RuntimeError("invalid response"))
    ).run_scenario("RUN", scenario())
    assert result.status == "polling_failed"


def test_partial_application_response(tmp_path):
    api = FakeAPI(submission={"investigation_id": None, "confidence": 0.2})
    assert (
        runner(tmp_path, api=api).run_scenario("RUN", scenario()).status
        == "partial_application_response"
    )


def test_persistence_failure_preserves_redacted_recovery_and_cleanup(tmp_path):
    database = FakeDatabase()
    result = runner(tmp_path, database=database, store=FakeStore(fail=True)).run_scenario(
        "RUN", scenario()
    )
    assert result.status == "persistence_failed"
    assert database.calls[-1] == "cleanup"
    with open(result.recovery_artifact, encoding="utf-8") as recovery_file:
        recovery = json.load(recovery_file)
    assert "secret" not in json.dumps(recovery).lower().replace("[redacted]", "")


def test_cleanup_after_investigation_failure(tmp_path):
    database = FakeDatabase()
    runner(
        tmp_path, database=database, api=FakeAPI(submit_error=RuntimeError("failed"))
    ).run_scenario("RUN", scenario())
    assert database.calls[-1] == "cleanup"


def test_interrupted_run_resume_selection():
    latest = latest_statuses([{"scenario_id": "A", "attempt": 1, "status": "interrupted"}])
    available = {"A", "B"}
    selected = {
        item
        for item in available
        if item not in latest or latest[item]["status"] in FAILED_STATUSES
    }
    assert selected == {"A", "B"}


def test_rerun_failed_scenarios_only():
    latest = latest_statuses(
        [
            {"scenario_id": "A", "attempt": 1, "status": "completed"},
            {"scenario_id": "B", "attempt": 1, "status": "timeout"},
        ]
    )
    assert {key for key, row in latest.items() if row["status"] in FAILED_STATUSES} == {"B"}


def test_same_database_concurrency_protection(tmp_path):
    database = FakeDatabase(delay=0.02)
    app = runner(tmp_path, database=database)
    app.config = replace(app.config, concurrency=2)
    results = app.run_many("RUN", [scenario(scenario_id="S1"), scenario(scenario_id="S2")])
    assert len(results) == 2
    assert not database.overlap


def test_secret_redaction():
    value = redact(
        {
            "authorization": "Bearer abc",
            "message": "password=hunter2",
            "url": "postgres://user:pw@host/db",
        }
    )
    rendered = json.dumps(value)
    assert "hunter2" not in rendered and "user:pw" not in rendered and "Bearer abc" not in rendered


def test_transient_api_retry(tmp_path):
    class RetryAPI(FakeAPI):
        calls = 0

        def submit(self, payload):
            self.calls += 1
            if self.calls == 1:
                raise TransientAPIError("rate limited")
            return super().submit(payload)

    result = runner(tmp_path, api=RetryAPI()).run_scenario("RUN", scenario())
    assert result.status == "completed" and result.retries == 1


def test_immutable_historical_runs_and_attempts():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    store = SQLAlchemyExecutionStore(factory)
    first_run = store.create_run(
        run_name="one", metadata={"application_commit": "a", "application_version": "1"}
    )
    second_run = store.create_run(
        run_name="two", metadata={"application_commit": "b", "application_version": "2"}
    )
    assert first_run != second_run
    app = EvaluationRunner(
        config=config("."),
        database=FakeDatabase(),
        api=FakeAPI(),
        store=store,
        sleeper=lambda _: None,
    )
    app.run_scenario(first_run, scenario())
    app.run_scenario(first_run, scenario())
    with Session(engine) as db:
        rows = (
            db.query(EvaluationScenarioExecutionModel)
            .order_by(EvaluationScenarioExecutionModel.attempt)
            .all()
        )
        assert [row.attempt for row in rows] == [1, 2]

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from legacydb_copilot.databases import DatabaseEngine
from legacydb_copilot.db import connector as connector_module
from legacydb_copilot.db.connector import ConnectionPool


class FakeConnector:
    created = []

    def __init__(self, database_engine, connection_string):
        self.database_engine = database_engine
        self.connection_string = connection_string
        self.disconnected = False
        self.disconnect_entered: Event | None = None
        self.disconnect_release: Event | None = None
        type(self).created.append(self)

    def disconnect(self):
        self.disconnected = True
        if self.disconnect_entered is not None:
            self.disconnect_entered.set()
        if self.disconnect_release is not None:
            assert self.disconnect_release.wait(timeout=5)


def install_fake_connector(monkeypatch) -> None:
    FakeConnector.created = []
    monkeypatch.setattr(connector_module, "DatabaseConnector", FakeConnector)


def create(pool, connection_id="connection-1", key="configuration-1"):
    return pool.get_or_create(
        connection_id,
        DatabaseEngine.SQLITE,
        "sqlite:///:memory:",
        configuration_key=key,
    )


def test_concurrent_get_or_create_constructs_one_connector(monkeypatch) -> None:
    install_fake_connector(monkeypatch)
    pool = ConnectionPool()

    with ThreadPoolExecutor(max_workers=12) as executor:
        connectors = list(executor.map(lambda _: create(pool), range(48)))

    assert len(FakeConnector.created) == 1
    assert all(connector is connectors[0] for connector in connectors)


def test_concurrent_lookup_during_invalidation_cannot_return_removed_connector(monkeypatch) -> None:
    install_fake_connector(monkeypatch)
    pool = ConnectionPool()
    connector = create(pool)
    entered = Event()
    release = Event()
    connector.disconnect_entered = entered
    connector.disconnect_release = release

    with ThreadPoolExecutor(max_workers=2) as executor:
        closing = executor.submit(pool.close, "connection-1")
        assert entered.wait(timeout=5)
        assert pool.get_existing("connection-1", configuration_key="configuration-1") is None
        release.set()
        closing.result(timeout=5)

    assert connector.disconnected is True


def test_configuration_fingerprint_change_rejects_and_recreates_connector(monkeypatch) -> None:
    install_fake_connector(monkeypatch)
    pool = ConnectionPool()
    original = create(pool, key="configuration-1")

    assert pool.get_existing("connection-1", configuration_key="configuration-2") is None
    replacement = create(pool, key="configuration-2")

    assert original.disconnected is True
    assert replacement is not original
    assert pool.get_existing("connection-1", configuration_key="configuration-2") is replacement


def test_close_all_clears_state_before_connectors_are_closed(monkeypatch) -> None:
    install_fake_connector(monkeypatch)
    pool = ConnectionPool()
    first = create(pool, "connection-1", "configuration-1")
    second = create(pool, "connection-2", "configuration-2")
    entered = Event()
    release = Event()
    first.disconnect_entered = entered
    first.disconnect_release = release

    with ThreadPoolExecutor(max_workers=2) as executor:
        closing = executor.submit(pool.close_all)
        assert entered.wait(timeout=5)
        assert pool.get_existing("connection-1", configuration_key="configuration-1") is None
        assert pool.get_existing("connection-2", configuration_key="configuration-2") is None
        release.set()
        closing.result(timeout=5)

    assert first.disconnected is True
    assert second.disconnected is True
    assert pool._connections == {}
    assert pool._cache_keys == {}


def test_closing_one_connection_does_not_block_lookup_for_another(monkeypatch) -> None:
    install_fake_connector(monkeypatch)
    pool = ConnectionPool()
    first = create(pool, "connection-1", "configuration-1")
    second = create(pool, "connection-2", "configuration-2")
    entered = Event()
    release = Event()
    first.disconnect_entered = entered
    first.disconnect_release = release

    with ThreadPoolExecutor(max_workers=2) as executor:
        closing = executor.submit(pool.close, "connection-1")
        assert entered.wait(timeout=5)
        assert pool.get_existing("connection-2", configuration_key="configuration-2") is second
        release.set()
        closing.result(timeout=5)

    assert first.disconnected is True
    assert second.disconnected is False

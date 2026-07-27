from legacydb_copilot.routers.investigation_states import router


def test_state_read_endpoints_are_registered() -> None:
    paths = {route.path for route in router.routes}

    assert "/investigations/{investigation_id}/state" in paths
    assert "/investigations/{investigation_id}/state/history" in paths
    assert "/investigations/{investigation_id}/agentic-steps" in paths

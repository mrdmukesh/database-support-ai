from pathlib import Path

WORKFLOW = Path(".github/workflows/azure-container-app.yml")


def test_azure_deployment_is_langgraph_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "environment: azure-low-cost" in workflow
    assert '"INVESTIGATION_ORCHESTRATOR_MODE=LANGGRAPH"' in workflow
    assert '"LANGGRAPH_ENABLED=true"' in workflow
    assert '"LANGGRAPH_MAX_CONCURRENT_RUNS=1"' in workflow
    assert '"LANGGRAPH_FALLBACK_TO_LEGACY=false"' in workflow
    assert '"LANGGRAPH_ROLLOUT_PERCENT=100"' in workflow
    assert '"LANGGRAPH_SHADOW_PERCENT=0"' in workflow
    assert "LANGGRAPH_ALLOWED_WORKSPACE_IDS" not in workflow
    assert "LANGGRAPH_ALLOWED_USER_IDS" not in workflow

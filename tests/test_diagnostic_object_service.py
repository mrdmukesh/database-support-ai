from legacydb_copilot.agents import object_ranking_agent, reasoning_agent
from legacydb_copilot.services import (
    evidence_verification_agent,
    metadata_search_service,
    safe_sql_service,
)
from legacydb_copilot.services.diagnostic_object_service import (
    contains_diagnostic_reference,
    diagnostic_object_names,
    is_diagnostic_object,
)


def test_diagnostic_classifier_is_domain_neutral() -> None:
    names = [
        "ops.delivery_failures",
        "finance.integration_outbox",
        "hr.audit_history",
        "core.customers",
    ]

    assert diagnostic_object_names(names) == names[:3]
    assert is_diagnostic_object("warehouse.job_runs")
    assert not is_diagnostic_object("warehouse.shipments")
    assert contains_diagnostic_reference(["Rows returned from ops.workflow_exceptions"])


def test_all_diagnostic_consumers_share_one_classifier() -> None:
    assert metadata_search_service.is_diagnostic_object is is_diagnostic_object
    assert object_ranking_agent.is_diagnostic_object is is_diagnostic_object
    assert safe_sql_service.is_diagnostic_object is is_diagnostic_object
    assert (
        evidence_verification_agent.contains_diagnostic_reference
        is contains_diagnostic_reference
    )
    assert reasoning_agent.contains_diagnostic_reference is contains_diagnostic_reference

from legacydb_copilot.services.safe_investigation_planner import (
    ActionOutcome,
    EntityScope,
    EnvironmentPolicy,
    EvidenceRequest,
    EvidenceRequestType,
    InvestigationBudget,
    PlannerStatus,
    PreviousAction,
    SafeInvestigationPlanner,
    action_fingerprint,
)


def request(
    question: str,
    request_type: EvidenceRequestType,
    *,
    scope: EntityScope = EntityScope.EXACT_KEY,
    key: str = "ID-42",
    gain: float = 0.8,
    cost: int = 1,
    broad: bool = False,
) -> EvidenceRequest:
    return EvidenceRequest(
        request_type=request_type,
        unresolved_question=question,
        entity_scope=scope,
        entity_type="Order",
        entity_key=key,
        expected_information_gain=gain,
        estimated_query_cost=cost,
        broad_scan=broad,
    )


def budget(*, used: int = 0, limit: int = 10) -> InvestigationBudget:
    return InvestigationBudget(
        queries_used=used,
        query_limit=limit,
        iterations_used=0,
        iteration_limit=5,
    )


def policy(**overrides) -> EnvironmentPolicy:
    values = {
        "environment": "evaluation",
        "policy_name": "evaluation_readonly",
        "allow_broad_scans": False,
        "max_query_cost": 10,
    }
    values.update(overrides)
    return EnvironmentPolicy(**values)


def test_priority_order_follows_investigation_sequence() -> None:
    candidates = [
        request("WORKFLOW", EvidenceRequestType.WORKFLOW_TRACE, gain=1),
        request("ACTUAL_STATE", EvidenceRequestType.STATUS_HISTORY, gain=1),
        request("EXPECTED_STATE", EvidenceRequestType.EXPECTED_STATE_CHECK, gain=0.4),
        request("AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP, gain=0.2),
    ]

    decision = SafeInvestigationPlanner().select_next(
        candidates=candidates,
        budget=budget(),
        policy=policy(),
    )

    assert decision.selected_request == candidates[3]
    assert decision.status is PlannerStatus.SELECTED


def test_duplicate_suppression_is_stable_for_reordered_filters() -> None:
    first = EvidenceRequest(
        request_type=EvidenceRequestType.RELATED_RECORDS,
        unresolved_question="RELATIONSHIPS",
        entity_scope=EntityScope.BOUNDED_RELATIONSHIP,
        entity_type="Order",
        entity_key="42",
        filters=(("status", "open"), ("tenant", "7")),
    )
    duplicate = EvidenceRequest(
        request_type=EvidenceRequestType.RELATED_RECORDS,
        unresolved_question=" relationships ",
        entity_scope=EntityScope.BOUNDED_RELATIONSHIP,
        entity_type="order",
        entity_key="42",
        filters=(("tenant", "7"), ("status", "open")),
    )
    assert action_fingerprint(first) == action_fingerprint(duplicate)

    decision = SafeInvestigationPlanner().select_next(
        candidates=(duplicate,),
        previous_actions=(
            PreviousAction(action_fingerprint(first), ActionOutcome.SUCCEEDED),
        ),
        budget=budget(),
        policy=policy(),
    )

    assert decision.status is PlannerStatus.NO_ELIGIBLE_ACTION
    assert decision.selected_request is None


def test_failed_action_is_followed_by_an_alternative() -> None:
    failed = request("ACTUAL_STATE", EvidenceRequestType.STATUS_HISTORY)
    alternative = request("RELATIONSHIPS", EvidenceRequestType.RELATED_RECORDS)

    decision = SafeInvestigationPlanner().select_next(
        candidates=(failed, alternative),
        previous_actions=(
            PreviousAction(action_fingerprint(failed), ActionOutcome.FAILED_PERMANENT),
        ),
        budget=budget(),
        policy=policy(),
    )

    assert decision.selected_request == alternative


def test_only_one_classified_transient_retry_is_allowed() -> None:
    candidate = request("ACTUAL_STATE", EvidenceRequestType.STATUS_HISTORY)
    fingerprint = action_fingerprint(candidate)
    planner = SafeInvestigationPlanner()

    retry = planner.select_next(
        candidates=(candidate,),
        previous_actions=(PreviousAction(fingerprint, ActionOutcome.FAILED_TRANSIENT),),
        budget=budget(),
        policy=policy(),
    )
    exhausted = planner.select_next(
        candidates=(candidate,),
        previous_actions=(
            PreviousAction(fingerprint, ActionOutcome.FAILED_TRANSIENT, attempts=2),
        ),
        budget=budget(),
        policy=policy(),
    )

    assert retry.status is PlannerStatus.SELECTED
    assert retry.retry_number == 1
    assert exhausted.status is PlannerStatus.NO_ELIGIBLE_ACTION


def test_budget_block_prevents_selection() -> None:
    decision = SafeInvestigationPlanner().select_next(
        candidates=(request("AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP),),
        budget=budget(used=2, limit=2),
        policy=policy(),
    )

    assert decision.status is PlannerStatus.QUERY_BUDGET_EXHAUSTED
    assert decision.selected_request is None


def test_production_policy_blocks_disallowed_action() -> None:
    candidate = request(
        "ACTUAL_STATE",
        EvidenceRequestType.STATUS_HISTORY,
        scope=EntityScope.BROAD,
        key="",
        broad=True,
    )
    decision = SafeInvestigationPlanner().select_next(
        candidates=(candidate,),
        budget=budget(),
        policy=policy(environment="production", policy_name="production_strict"),
    )

    assert decision.status is PlannerStatus.POLICY_BLOCKED
    assert "production_strict" in decision.selection_reason


def test_narrow_key_is_preferred_over_broad_scan() -> None:
    broad = request(
        "ACTUAL_STATE",
        EvidenceRequestType.STATUS_HISTORY,
        scope=EntityScope.BROAD,
        key="",
        gain=0.95,
        broad=True,
    )
    narrow = request(
        "ACTUAL_STATE",
        EvidenceRequestType.STATUS_HISTORY,
        scope=EntityScope.EXACT_KEY,
        gain=0.75,
    )
    decision = SafeInvestigationPlanner().select_next(
        candidates=(broad, narrow),
        budget=budget(),
        policy=policy(allow_broad_scans=True),
    )

    assert decision.selected_request == narrow


def test_request_is_logical_and_contains_no_sql_field() -> None:
    candidate = request("AFFECTED_ENTITY", EvidenceRequestType.ENTITY_LOOKUP)

    assert "sql" not in candidate.__dataclass_fields__
    assert candidate.request_type is EvidenceRequestType.ENTITY_LOOKUP

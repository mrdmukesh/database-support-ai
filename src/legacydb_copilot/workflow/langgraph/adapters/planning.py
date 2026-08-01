from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
)
from legacydb_copilot.services.safe_sql_service import PlannedQuery
from legacydb_copilot.workflow.langgraph.enums import ObjectDisposition
from legacydb_copilot.workflow.langgraph.state import (
    DatabaseObjectRef,
    InvestigationPlanStep,
    InvestigationState,
    QueryRecord,
)

QueryGenerator = Callable[[InvestigationPlanStep, InvestigationState], list[PlannedQuery]]


@dataclass(frozen=True)
class PlanningAdapter:
    query_generator: QueryGenerator
    planner: SafeInvestigationPlanner = SafeInvestigationPlanner()

    def __call__(self, state: InvestigationState) -> dict[str, Any]:
        if state["cancel_requested"]:
            return {"stop_reason": "Cancellation requested."}
        next_round = state["planning_round"] + 1
        if next_round > state["max_planning_rounds"]:
            return {"replan_reason": "Planning-round limit reached."}
        remaining = max(0, state["max_queries"] - state["query_count"])
        completed = set(state["completed_plan_steps"])
        prior = [
            PreviousAction(step.action_fingerprint, ActionOutcome.SUCCEEDED)
            for step in state["investigation_plan"]
            if step.step_id in completed and step.action_fingerprint
        ]
        candidates = [
            _request(item, state)
            for item in [*state["required_objects"], *state["optional_objects"]]
            if item.qualified_name not in state["successful_objects"]
        ]
        steps: list[InvestigationPlanStep] = []
        proposed: list[QueryRecord] = []
        fingerprints = list(state["plan_fingerprints"])
        for _ in range(remaining):
            decision = self.planner.select_next(
                candidates=candidates,
                previous_actions=prior,
                budget=InvestigationBudget(
                    queries_used=state["query_count"] + len(proposed),
                    query_limit=state["max_queries"],
                    iterations_used=next_round - 1,
                    iteration_limit=state["max_planning_rounds"],
                ),
                policy=_policy(state),
            )
            if decision.status is not PlannerStatus.SELECTED or decision.selected_request is None:
                break
            request = decision.selected_request
            target = _find_object(state, request.object_name)
            step_id = f"PLAN-{next_round}-{len(steps) + 1}"
            step = InvestigationPlanStep(
                step_id=step_id,
                objective=f"Inspect {request.object_name}",
                database=target.database if target else state["requested_database"],
                object_name=request.object_name,
                object_type=target.object_type if target else "TABLE",
                evidence_sought=request.unresolved_question,
                query_intent=request.request_type.value,
                required=request.required_for_goal,
                success_condition="Durable evidence or conclusive verified absence.",
                join_justification=request.relationship_name,
                relationship_source=request.relationship_name,
                required_objects=(request.object_name,) if request.required_for_goal else (),
                inspection_only=bool(target and target.inspection_only),
                planning_round=next_round,
                action_fingerprint=decision.action_fingerprint,
            )
            steps.append(step)
            prior.append(PreviousAction(decision.action_fingerprint, ActionOutcome.SELECTED))
            for planned in self.query_generator(step, state):
                digest = hashlib.sha256(planned.sql.encode()).hexdigest()
                if digest in state["rejected_query_hashes"]:
                    continue
                proposed.append(
                    QueryRecord(
                        query_id=planned.query_id or f"Q-{next_round}-{len(proposed) + 1}",
                        plan_step_id=step_id,
                        sanitized_sql=planned.sql,
                        query_hash=digest,
                        parameter_metadata={
                            key: type(value).__name__ for key, value in planned.parameters.items()
                        },
                        target_database=step.database,
                        referenced_objects=(step.object_name,),
                    )
                )
            fingerprints.append(decision.action_fingerprint)
        round_hash = hashlib.sha256(
            "|".join(sorted(step.action_fingerprint for step in steps)).encode()
        ).hexdigest()
        repeated = bool(steps) and round_hash in state["plan_fingerprints"]
        if repeated or not steps:
            return {
                "planning_round": next_round,
                "no_progress_rounds": state["no_progress_rounds"] + 1,
                "replan_reason": "Repeated plan or no safe additional work.",
                "plan_fingerprints": [*fingerprints, round_hash] if round_hash else fingerprints,
            }
        return {
            "investigation_plan": [*state["investigation_plan"], *steps],
            "proposed_queries": proposed,
            "planning_round": next_round,
            "plan_fingerprints": [*fingerprints, round_hash],
            "no_progress_rounds": 0,
            "replan_reason": "",
        }


def _request(item: DatabaseObjectRef, state: InvestigationState) -> EvidenceRequest:
    entity_key = state["resolved_entities"][0].matched_value if state["resolved_entities"] else ""
    request_type = (
        EvidenceRequestType.PROCEDURE_DEFINITION
        if item.inspection_only
        else EvidenceRequestType.ENTITY_LOOKUP
    )
    relationship = next(
        (
            f"{edge.source_object}.{edge.source_column}->{edge.target_object}.{edge.target_column}"
            for edge in state["relationship_edges"]
            if item.object_name.casefold()
            in {edge.source_object.casefold(), edge.target_object.casefold()}
        ),
        "",
    )
    return EvidenceRequest(
        request_type=request_type,
        unresolved_question=f"Required evidence for {item.qualified_name}",
        entity_scope=EntityScope.OBJECT_METADATA if item.inspection_only else EntityScope.EXACT_KEY,
        entity_type="business_identifier",
        entity_key=entity_key or item.object_name,
        object_name=item.qualified_name,
        relationship_name=relationship,
        supporting_evidence_refs=tuple(state["evidence_ids"]),
        required_for_goal=item.disposition == ObjectDisposition.REQUIRED,
    )


def _find_object(state: InvestigationState, name: str) -> DatabaseObjectRef | None:
    return next((item for item in state["selected_objects"] if item.qualified_name == name), None)


def _policy(state: InvestigationState) -> EnvironmentPolicy:
    policy = state["environment_policy"]
    return EnvironmentPolicy(
        environment=state["environment"],
        policy_name=policy.policy_name or "LANGGRAPH_EXISTING_POLICY",
        allow_broad_scans=policy.allow_full_table_scan,
    )

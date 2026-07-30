from __future__ import annotations

from dataclasses import replace

import pytest

from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis
from legacydb_copilot.workflow.langgraph.adapters.relationship_discovery import (
    DiscoverySnapshot,
    InferredRelationship,
    RelationshipDiscoveryAdapter,
)
from legacydb_copilot.workflow.langgraph.contracts import OperationalNodeError
from legacydb_copilot.workflow.langgraph.enums import (
    EntityResolutionStatus,
    RelationshipVerification,
)
from legacydb_copilot.workflow.langgraph.state import (
    ResolvedEntityRecord,
    create_initial_investigation_state,
)


def table(name, fks=(), indexes=()):
    return TableMetadata(name, ["id", "parent_id"], 1, ["id"], list(fks), list(indexes))


def fk(target, source="parent_id", target_column="id"):
    return {"columns": [source], "referred_table": target, "referred_columns": [target_column]}


def state():
    value = create_initial_investigation_state(investigation_id="i", workspace_id="w", question="q")
    value["entity_resolution_status"] = EntityResolutionStatus.RESOLVED
    value["resolved_entities"] = [
        ResolvedEntityRecord(
            entity_type="business_identifier",
            business_key="1",
            matched_value="1",
            table="a",
            column="id",
            matching_method="exact",
            evidence_id="E-1",
        )
    ]
    return value


def result(tables, **kwargs):
    return DiscoverySnapshot(MetadataSearchResult(list(tables), [], [], "v", **kwargs))


def run(snapshot, **kwargs):
    return RelationshipDiscoveryAdapter(lambda _state: snapshot, lambda _state: None, **kwargs)(
        state()
    )


def proc(name="p", reads=("a",), writes=(), dynamic=False):
    return ProcedureAnalysis(
        name,
        True,
        list(reads),
        list(writes),
        0,
        1 if writes else 0,
        0,
        0,
        0,
        0,
        0,
        False,
        0,
        0,
        0,
        dynamic,
        False,
        False,
        "Low",
        "Low",
        1,
        "Low",
        [],
        "",
        object_type="PROCEDURE",
    )


def test_tc_rl_01_foreign_key():
    update = run(
        result(
            [
                table("a", [fk("b")], [{"unique": True, "column_names": ["id"]}]),
                table("b"),
            ]
        )
    )
    kinds = {edge.relationship_type for edge in update["relationship_edges"]}
    assert {"foreign_key", "primary_key", "unique_key"} <= kinds


def test_tc_rl_02_self_referencing_foreign_key():
    update = run(result([table("a", [fk("a")])]))
    assert update["relationship_edges"][0].relationship_type == "self_foreign_key"


def test_tc_rl_03_multi_hop_traversal():
    update = run(result([table("a", [fk("b")]), table("b", [fk("c")]), table("c")]))
    assert {item.object_name for item in update["selected_objects"]} == {"a", "b", "c"}


def test_tc_rl_04_duplicate_edge_is_deduplicated():
    update = run(result([table("a", [fk("b"), fk("b")]), table("b")]))
    foreign_keys = [
        edge for edge in update["relationship_edges"] if edge.relationship_type == "foreign_key"
    ]
    assert len(foreign_keys) == 1


def test_tc_rl_05_cycle_is_bounded():
    update = run(result([table("a", [fk("b")]), table("b", [fk("a")])]))
    assert len(update["selected_objects"]) == 2


def test_tc_rl_06_object_limit_records_gap():
    update = run(result([table("a", [fk("b")]), table("b")]), max_objects=1)
    assert any(g.gap_type == "object_limit" for g in update["metadata_gaps"])


def test_tc_rl_07_depth_limit_records_gap():
    update = run(result([table("a", [fk("b")]), table("b")]), max_depth=0)
    assert any(g.gap_type == "depth_limit" for g in update["metadata_gaps"])


def test_tc_rl_08_inferred_relationship_remains_inferred():
    snapshot = replace(
        result([table("a")]), inferred_relationships=(InferredRelationship("a", "id", "b", "a_id"),)
    )
    edge = next(
        edge
        for edge in run(snapshot)["relationship_edges"]
        if edge.relationship_type == "business_key"
    )
    assert edge.verification == RelationshipVerification.INFERRED


def test_tc_rl_09_procedure_dependency():
    snapshot = replace(result([table("a")]), procedures=(proc(),))
    assert any(
        edge.relationship_type == "procedure_read_dependency"
        for edge in run(snapshot)["relationship_edges"]
    )


def test_tc_rl_10_mutating_procedure_is_unsafe():
    snapshot = replace(result([table("a")]), procedures=(proc(writes=("a",)),))
    procedure = next(
        item for item in run(snapshot)["selected_objects"] if item.object_type == "PROCEDURE"
    )
    assert procedure.inspection_only and procedure.contains_mutation and procedure.unsafe_to_execute


def test_tc_rl_11_select_only_procedure_is_inspection_only():
    snapshot = replace(result([table("a")]), procedures=(proc(),))
    procedure = next(
        item for item in run(snapshot)["selected_objects"] if item.object_type == "PROCEDURE"
    )
    assert procedure.inspection_only and not procedure.unsafe_to_execute


def test_tc_rl_12_dynamic_sql_is_unsafe():
    snapshot = replace(result([table("a")]), procedures=(proc(dynamic=True),))
    procedure = next(
        item for item in run(snapshot)["selected_objects"] if item.object_type == "PROCEDURE"
    )
    assert procedure.contains_dynamic_sql and procedure.unsafe_to_execute


def test_tc_rl_13_view_dependency():
    snapshot = replace(result([table("a")]), view_dependencies={"v_a": ("a",)})
    assert any(
        edge.relationship_type == "view_dependency" for edge in run(snapshot)["relationship_edges"]
    )


def test_tc_rl_14_partial_metadata_permission_records_gap():
    snapshot = replace(result([table("a")]), inaccessible_objects=("secret_table",))
    assert any(g.gap_type == "metadata_permission" for g in run(snapshot)["metadata_gaps"])


def test_tc_rl_15_missing_object_records_blocking_gap():
    update = run(result([]))
    assert update["metadata_gaps"][0].blocking


def test_tc_rl_16_cross_database_object_keeps_location():
    update = run(result([table("other.dbo.a")]))
    assert update["metadata_gaps"][0].gap_type == "missing_object"


def test_tc_rl_17_required_and_optional_classification():
    update = run(result([table("a", [fk("b")]), table("b")]))
    assert len(update["required_objects"]) == 1 and len(update["optional_objects"]) == 1


def test_tc_rl_18_authorization_failure_is_operational():
    adapter = RelationshipDiscoveryAdapter(
        lambda _state: result([table("a")]),
        lambda _state: (_ for _ in ()).throw(PermissionError("no")),
    )
    with pytest.raises(OperationalNodeError) as error:
        adapter(state())
    assert error.value.code == "METADATA_ACCESS_DENIED"

from __future__ import annotations

from legacydb_copilot.services.evidence_verification_agent import (
    SuggestedVerificationCheck,
    adjust_confidence_with_verification,
    execute_verification_check,
    _matching_verification_evidence,
    _verification_parameters,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult


class RecordingConnector:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute_read_only_query(self, sql, limit=25, parameters=None):
        self.calls.append((sql, limit, parameters))
        return self.rows


def _run(connector, *, sql="SELECT AssetCode, RetiredAt FROM ops.Asset WHERE AssetCode = :resolved_identifier", value="AST-2042"):
    return execute_verification_check(
        connector=connector,
        claim="The reported NULL condition is reproduced from live evidence.",
        verification_sql=sql,
        parameters={"resolved_identifier": value},
        expected_result="Rows returned",
        source="SQL-7",
        verified_by="reviewer@example.com",
    )[0]


def test_suggested_verification_check_persists_named_parameter_context() -> None:
    check = SuggestedVerificationCheck(
        claim="Generic entity check",
        verification_sql="SELECT AssetCode FROM ops.Asset WHERE AssetCode = :resolved_identifier",
        expected_result="Rows returned",
        risk_level="Read-only",
        source="SQL-7",
        parameters={"resolved_identifier": "AST-2042"},
        parameter_types={"resolved_identifier": "str"},
        evidence_id="SQL-7",
        entity_table="ops.Asset",
        resolved_entity_scope="exact_entity",
        identifier_column="AssetCode",
        identifier_value="AST-2042",
    )

    assert check.parameters == {"resolved_identifier": "AST-2042"}
    assert check.parameter_types == {"resolved_identifier": "str"}
    assert check.identifier_column == "AssetCode"
    assert check.identifier_value == "AST-2042"


def test_normalized_sql_matches_parameter_bearing_evidence_instead_of_empty_duplicate() -> None:
    sql = "SELECT BusinessKey, DateOfBirth FROM dbo.Employee WHERE BusinessKey = :resolved_identifier"
    evidence = [
        EvidenceResult("duplicate", sql, [{"BusinessKey": "wrong"}]),
        EvidenceResult(
            "authoritative",
            "SELECT TOP (25) [BusinessKey], [DateOfBirth] FROM [dbo].[Employee] WHERE [BusinessKey] = :resolved_identifier",
            [{"BusinessKey": "E1001", "DateOfBirth": None}],
            parameters={"resolved_identifier": "E1001"},
            entity_table="dbo.Employee",
            identifier_column="BusinessKey",
            identifier_value="E1001",
        ),
    ]

    matched = _matching_verification_evidence(sql, evidence)

    assert matched is evidence[1]
    assert _verification_parameters(sql, matched) == {"resolved_identifier": "E1001"}


def test_identifier_scope_recovers_single_missing_named_bind_without_domain_hardcoding() -> None:
    sql = "SELECT DeviceSerial FROM inventory.Device WHERE DeviceSerial = :device_key"
    evidence = EvidenceResult(
        "generic scope",
        sql,
        [{"DeviceSerial": "DEV-9"}],
        parameters={},
        entity_table="inventory.Device",
        identifier_column="DeviceSerial",
        identifier_value="DEV-9",
    )

    assert _verification_parameters(sql, evidence) == {"device_key": "DEV-9"}


def test_human_approved_execution_reuses_parameters_and_preserves_typed_rows() -> None:
    connector = RecordingConnector([{"AssetCode": "AST-2042", "RetiredAt": None, "Revision": 3}])

    result = _run(connector)

    assert connector.calls[0][2] == {"resolved_identifier": "AST-2042"}
    assert result.actual_result == {
        "columns": ["AssetCode", "RetiredAt", "Revision"],
        "rows": [{"AssetCode": "AST-2042", "RetiredAt": None, "Revision": 3}],
        "row_count": 1,
    }
    assert "RetiredAt = NULL" in result.actual_result_summary
    assert result.status == "Verified"
    assert result.confidence_impact == "No confidence cap. Verification supports the RCA."


def test_missing_parameter_fails_before_database_execution() -> None:
    connector = RecordingConnector([])
    result = execute_verification_check(
        connector=connector,
        claim="Generic entity check",
        verification_sql="SELECT * FROM ops.Asset WHERE AssetCode = :resolved_identifier",
        parameters={},
        expected_result="Rows returned",
        source="SQL-7",
        verified_by="reviewer@example.com",
    )[0]

    assert connector.calls == []
    assert result.status == "VERIFICATION_PARAMETER_MISSING"
    assert result.missing_parameters == ("resolved_identifier",)
    assert "resolved_identifier" in result.actual_result_summary


def test_successful_verification_does_not_cap_confidence() -> None:
    result = _run(RecordingConnector([{"AssetCode": "AST-2042", "RetiredAt": None}]))
    adjusted, notes = adjust_confidence_with_verification(0.8, [result])
    assert adjusted >= 0.8
    assert all("limited" not in note.lower() for note in notes)


def test_real_zero_row_result_is_not_enough_evidence() -> None:
    result = _run(RecordingConnector([]))
    assert result.status == "Not Enough Evidence"


def test_generic_entity_and_identifier_are_not_domain_hardcoded() -> None:
    connector = RecordingConnector([{"DeviceSerial": "DEV-9", "DisabledOn": None}])
    result = _run(
        connector,
        sql="SELECT DeviceSerial, DisabledOn FROM inventory.Device WHERE DeviceSerial = :resolved_identifier",
        value="DEV-9",
    )
    assert connector.calls[0][2] == {"resolved_identifier": "DEV-9"}
    assert result.actual_result["columns"] == ["DeviceSerial", "DisabledOn"]

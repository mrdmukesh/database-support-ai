import re

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.safe_sql_service import plan_safe_queries, validate_read_only_sql


def _transfer_metadata() -> MetadataSearchResult:
    transfers = TableMetadata(
        "eval.transfers",
        ["TransfersId", "AccountsId", "BusinessKey", "Status", "EventTime"],
        25,
        ["TransfersId"],
        foreign_keys=[
            {
                "columns": ["AccountsId"],
                "referred_table": "eval.accounts",
                "referred_columns": ["AccountsId"],
            }
        ],
        indexes=[],
    )
    accounts = TableMetadata(
        "eval.accounts",
        ["AccountsId", "BusinessKey", "AccountName", "Status"],
        18,
        ["AccountsId"],
        foreign_keys=[],
        indexes=[],
    )
    transactions = TableMetadata(
        "eval.transactions",
        ["TransactionsId", "TransfersId", "AccountsId", "BusinessKey", "Status"],
        16,
        ["TransactionsId"],
        foreign_keys=[
            {
                "columns": ["TransfersId"],
                "referred_table": "eval.transfers",
                "referred_columns": ["TransfersId"],
            },
            {
                "columns": ["AccountsId"],
                "referred_table": "eval.accounts",
                "referred_columns": ["AccountsId"],
            },
        ],
        indexes=[],
    )
    audit_history = TableMetadata(
        "eval.audit_history",
        ["AuditHistoryId", "TransfersId", "AccountsId", "BusinessKey", "Status"],
        14,
        ["AuditHistoryId"],
        foreign_keys=[
            {
                "columns": ["TransfersId"],
                "referred_table": "eval.transfers",
                "referred_columns": ["TransfersId"],
            }
        ],
        indexes=[],
    )
    return MetadataSearchResult(
        tables=[transfers, accounts, transactions, audit_history],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )


def _duplicate_metadata() -> MetadataSearchResult:
    accounts = TableMetadata(
        "eval.accounts",
        ["AccountsId", "BusinessKey", "AccountName", "Status"],
        22,
        ["AccountsId"],
        foreign_keys=[],
        indexes=[],
    )
    transactions = TableMetadata(
        "eval.transactions",
        ["TransactionsId", "AccountsId", "BusinessKey", "Status", "EventTime"],
        20,
        ["TransactionsId"],
        foreign_keys=[
            {
                "columns": ["AccountsId"],
                "referred_table": "eval.accounts",
                "referred_columns": ["AccountsId"],
            }
        ],
        indexes=[],
    )
    return MetadataSearchResult(
        tables=[accounts, transactions],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )


def _join_queries(queries: list[str]) -> list[str]:
    return [sql for sql in queries if re.search(r"\bjoin\b", sql, re.I)]


def _assert_join_columns_are_qualified(sql: str) -> None:
    select_clause = re.search(r"select\s+(.*?)\s+from\s+", sql, re.I | re.S)
    assert select_clause, f"expected SELECT clause in SQL: {sql}"
    lowered = select_clause.group(1).lower()
    # The relationship planner uses aliases t/s or p/c for JOIN queries.
    assert any(prefix in lowered for prefix in ("t.", "s.", "p.", "c.")), sql


def test_transfers_accounts_join_select_where_and_order_by_use_aliases() -> None:
    metadata = _transfer_metadata()
    entities = extract_entities("Investigate transfer TRF-3101 across accounts and transactions")
    planned = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    sql = next(query.sql for query in planned if "JOIN eval.accounts s" in query.sql)
    _assert_join_columns_are_qualified(sql)
    assert "WHERE CAST(t.BusinessKey AS NVARCHAR(MAX)) = 'TRF-3101'" in sql
    assert "ORDER BY s." in sql
    assert not re.search(r"(?<![a-zA-Z0-9_]\.)\bAccountsId\b", sql)


def test_transfers_audit_history_join_uses_qualified_identifiers() -> None:
    metadata = _transfer_metadata()
    entities = extract_entities("Investigate transfer TRF-3101 with audit history")
    planned = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    sql = next(query.sql for query in planned if "JOIN eval.audit_history s" in query.sql)
    _assert_join_columns_are_qualified(sql)
    assert "WHERE CAST(t.BusinessKey AS NVARCHAR(MAX)) = 'TRF-3101'" in sql
    assert "ORDER BY s." in sql


def test_transactions_accounts_duplicate_flow_uses_qualified_join_columns() -> None:
    metadata = _duplicate_metadata()
    entities = extract_entities("Find duplicate transactions for account ACC-42")
    planned = plan_safe_queries(InvestigationIntent.DUPLICATE_DATA, metadata, entities)

    join_sql = _join_queries([query.sql for query in planned])
    assert join_sql
    assert any("JOIN eval.transactions c" in sql for sql in join_sql)
    for sql in join_sql:
        _assert_join_columns_are_qualified(sql)
        if " where " in sql.lower():
            assert " p." in sql or " c." in sql


def test_duplicate_column_names_are_never_unqualified_in_join_queries() -> None:
    metadata = _transfer_metadata()
    entities = extract_entities("Investigate transfer TRF-3101 with account and transaction linkage")
    planned = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    for sql in _join_queries([query.sql for query in planned]):
        _assert_join_columns_are_qualified(sql)
        assert not re.search(r"(?<![a-zA-Z0-9_]\.)\b(AccountsId|BusinessKey|Status)\b", sql)


def test_sql_server_join_queries_pass_safety_validation() -> None:
    metadata = _transfer_metadata()
    entities = extract_entities("Investigate transfer TRF-3101 with accounts, transactions and audit history")
    planned = plan_safe_queries(InvestigationIntent.PRODUCTION_INVESTIGATION, metadata, entities)

    join_sql = _join_queries([query.sql for query in planned])
    assert join_sql
    for sql in join_sql:
        validate_read_only_sql(sql)

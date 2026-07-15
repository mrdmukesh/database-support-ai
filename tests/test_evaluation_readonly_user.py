from __future__ import annotations

from evaluation_databases.provision_readonly_user import DATABASES, USERNAME, readonly_user_sql


def test_reader_is_limited_to_five_evaluation_databases() -> None:
    assert DATABASES == ("EvalPayroll", "EvalClinic", "EvalOrders", "EvalBanking", "EvalShipping")


def test_reader_sql_grants_only_read_access_and_denies_mutation() -> None:
    sql = readonly_user_sql("safe-reader-password")
    normalized = " ".join(sql.upper().split())
    assert f"ALTER ROLE [DB_DATAREADER] ADD MEMBER [{USERNAME.upper()}]" in normalized
    assert f"DENY INSERT, UPDATE, DELETE, EXECUTE TO [{USERNAME.upper()}]" in normalized
    assert "DB_DATAWRITER" not in normalized
    assert "GRANT EXECUTE" not in normalized
    assert "GRANT CONTROL" not in normalized


def test_reader_password_is_sql_escaped() -> None:
    sql = readonly_user_sql("reader'password")
    assert "reader''password" in sql
    assert "reader'password" not in sql

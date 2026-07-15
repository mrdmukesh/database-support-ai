from __future__ import annotations

import os
import subprocess

DATABASES = ("EvalPayroll", "EvalClinic", "EvalOrders", "EvalBanking", "EvalShipping")
USERNAME = "legacydb_eval_reader"


def readonly_user_sql(password: str) -> str:
    escaped = password.replace("'", "''")
    return f"""
IF USER_ID(N'{USERNAME}') IS NULL
    EXEC(N'CREATE USER [{USERNAME}] WITH PASSWORD = ''{escaped}''');
ELSE
    EXEC(N'ALTER USER [{USERNAME}] WITH PASSWORD = ''{escaped}''');
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members drm
    JOIN sys.database_principals role_principal ON role_principal.principal_id = drm.role_principal_id
    JOIN sys.database_principals member_principal ON member_principal.principal_id = drm.member_principal_id
    WHERE role_principal.name = N'db_datareader' AND member_principal.name = N'{USERNAME}'
)
    ALTER ROLE [db_datareader] ADD MEMBER [{USERNAME}];
DENY INSERT, UPDATE, DELETE, EXECUTE TO [{USERNAME}];
""".strip()


def main() -> None:
    server = os.environ["EVAL_SQL_SERVER"]
    admin = os.environ["EVAL_SQL_ADMIN"]
    admin_password = os.environ["EVAL_SQL_PASSWORD"]
    reader_password = os.environ["EVAL_READER_PASSWORD"]
    query = readonly_user_sql(reader_password)
    for database in DATABASES:
        env = dict(os.environ)
        env["SQLCMDPASSWORD"] = admin_password
        completed = subprocess.run(
            ["sqlcmd", "-S", server, "-U", admin, "-C", "-b", "-d", database],
            input=query + "\nGO\n",
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if completed.returncode:
            raise RuntimeError(f"Read-only user provisioning failed for {database} (sqlcmd exit {completed.returncode})")
        print(f"configured read-only user in {database}")


if __name__ == "__main__":
    main()

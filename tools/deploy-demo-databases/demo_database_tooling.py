"""Safety primitives for the Demo Evaluation Databases V2 deployment tools."""

from __future__ import annotations

import json
import re
from pathlib import Path

APPROVED_DATABASES = {
    "Banking": "DemoBankingV2",
    "Payroll": "DemoPayrollV2",
    "Orders": "DemoOrdersV2",
    "Shipping": "DemoShippingV2",
    "Clinic": "DemoClinicV2",
}
INSTALL_ORDER = (
    "Tables.sql",
    "ForeignKeys.sql",
    "SeedData.sql",
    "Views.sql",
    "StoredProcedures.sql",
    "Functions.sql",
    "Triggers.sql",
)
LEGACY_PATTERN = re.compile(
    r"\b(?:Eval|EvalDemo)(?:Banking|Payroll|Orders|Shipping|Clinic)\b", re.IGNORECASE
)
DESTRUCTIVE_PATTERN = re.compile(
    r"\b(?:DROP\s+DATABASE|ALTER\s+DATABASE\b[\s\S]*?\bSINGLE_USER\b|ROLLBACK\s+IMMEDIATE)\b",
    re.IGNORECASE,
)
SECRET_PATTERN = re.compile(
    r"(?i)(password|pwd|access[_-]?token|refresh[_-]?token|authorization|sqlcmdpassword)"
    r"(\s*[=:]\s*)([^\s;,]+)"
)


def assert_approved_database(name: str) -> None:
    if name not in APPROVED_DATABASES.values():
        raise ValueError(f"Database is not approved for demo deployment: {name}")


def redact(text: str) -> str:
    return SECRET_PATTERN.sub(r"\1\2[REDACTED]", text)


def find_destructive_sql(text: str) -> list[str]:
    return [match.group(0) for match in DESTRUCTIVE_PATTERN.finditer(text)]


def validate_package(package_path: Path) -> dict:
    failures: list[str] = []
    metadata_names: dict[str, list[str]] = {}
    for filename in ("manifest.json", "ValidationReport.json"):
        try:
            data = json.loads((package_path / filename).read_text(encoding="utf-8-sig"))
            metadata_names[filename] = list(data["databases"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            failures.append(f"{filename}: invalid JSON/package metadata: {exc}")

    expected_names = set(APPROVED_DATABASES.values())
    for filename, names in metadata_names.items():
        if set(names) != expected_names or len(names) != len(expected_names):
            failures.append(f"{filename}: database definitions do not match the approved allowlist")

    for folder, database in APPROVED_DATABASES.items():
        folder_path = package_path / folder
        for script in INSTALL_ORDER:
            path = folder_path / script
            if not path.is_file():
                failures.append(f"{folder}: missing {script}")
                continue
            text = path.read_text(encoding="utf-8-sig")
            if LEGACY_PATTERN.search(text):
                failures.append(f"{path}: legacy database name")
            use_names = re.findall(r"(?im)^\s*USE\s+\[([^\]]+)\]", text)
            if use_names != [database]:
                failures.append(f"{path}: expected exactly USE [{database}]")
            if find_destructive_sql(text):
                failures.append(f"{path}: destructive SQL in Azure chain")
        create_script = folder_path / "CreateDatabase.sql"
        if not create_script.is_file():
            failures.append(f"{folder}: missing local-only CreateDatabase.sql")

    return {
        "status": "PASS" if not failures else "FAIL",
        "approved_databases": list(APPROVED_DATABASES.values()),
        "installation_order": list(INSTALL_ORDER),
        "failures": failures,
    }


def deployment_result(database: str, *, exists: bool, what_if: bool) -> dict:
    assert_approved_database(database)
    status = (
        "SKIPPED_ALREADY_EXISTS"
        if exists
        else ("WOULD_CREATE" if what_if else "PENDING_CREATE")
    )
    return {"database": database, "status": status}


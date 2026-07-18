from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "evaluation" / "Resolve-ScenarioInventory.ps1"
SHELLS = list(dict.fromkeys(
    path
    for name in ("powershell.exe", "pwsh.exe", "pwsh", "powershell")
    if (path := shutil.which(name))
))


def invoke(shell: str, value) -> subprocess.CompletedProcess[str]:
    raw = json.dumps(value).replace("'", "''")
    command = (
        "Set-StrictMode -Version Latest; "
        f". '{HELPER}'; "
        f"$value = '{raw}' | ConvertFrom-Json; "
        "$items = @(ConvertTo-ValidatedScenarioInventory -InputObject $value); "
        "$domains = @(Get-ScenarioInventoryDomains -Scenarios $items); "
        "[pscustomobject]@{ids=@($items | ForEach-Object {$_.scenario_id}); domains=$domains} | ConvertTo-Json -Compress"
    )
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )


@pytest.mark.parametrize("shell", SHELLS)
def test_one_scenario_under_strict_mode(shell: str) -> None:
    result = invoke(shell, {"domain": "alpha", "scenario_id": "one"})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ids": ["one"], "domains": ["alpha"]}


@pytest.mark.parametrize("shell", SHELLS)
def test_multiple_scenarios_preserve_order(shell: str) -> None:
    result = invoke(shell, [
        {"domain": "beta", "scenario_id": "two"},
        {"domain": "alpha", "scenario_id": "one"},
    ])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ids"] == ["two", "one"]


@pytest.mark.parametrize("value", [
    {"scenario_id": "missing-domain"},
    None,
    "malformed-manifest-shape",
])
@pytest.mark.parametrize("shell", SHELLS)
def test_invalid_inventory_fails_descriptively(shell: str, value) -> None:
    result = invoke(shell, value)
    assert result.returncode != 0
    assert "scenario" in result.stderr.lower()


def test_supported_powershell_is_available() -> None:
    assert SHELLS, "Windows PowerShell 5.1 or PowerShell 7 is required"

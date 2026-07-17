from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("evaluation/Run-125ScenarioBenchmark.ps1")


def test_latest_result_extraction_uses_persisted_status_and_errors() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'getattr(row, "investigation_status", None)' in text
    assert 'getattr(row, "errors_json", None)' in text
    assert '"Unable to parse persisted errors_json"' in text
    assert 'getattr(row, "failure", None)' not in text


def test_summary_counts_attempts_unique_scenarios_and_writes_detail(tmp_path) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    helper = re.search(r"\$summaryHelper = @'\r?\n(.*?)\r?\n'@", text, re.S).group(1)
    csv_path = tmp_path / "benchmark-progress.csv"
    fields = [
        "Timestamp", "Domain", "ScenarioId", "ResultId", "RunId", "InvestigationId",
        "RowStatus", "InvestigationStatus", "CanonicalEntity", "BenchmarkValidity",
        "DeterministicScore", "Classification", "AIJudgeScore", "HumanReviewRequired",
        "Failure", "AIInvoked", "AIOutcome", "AISkipReason", "AIDiagnosticCategory",
        "LLMModelName", "PromptVersion", "InputTokens", "OutputTokens",
    ]
    rows = [
        dict.fromkeys(fields, "") | {"Timestamp": "1", "Domain": "banking", "ScenarioId": "one", "RowStatus": "invalid_configuration"},
        dict.fromkeys(fields, "") | {"Timestamp": "2", "Domain": "banking", "ScenarioId": "one", "RowStatus": "invalid_configuration", "InvestigationStatus": "INSUFFICIENT_DATABASE_EVIDENCE", "Failure": "missing tokens"},
        dict.fromkeys(fields, "") | {"Timestamp": "3", "Domain": "orders", "ScenarioId": "two", "RowStatus": "completed", "BenchmarkValidity": "valid", "Classification": "pass", "DeterministicScore": "80", "AIJudgeScore": "90"},
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary_path, md_path, detail_path = (tmp_path / name for name in ("summary.json", "summary.md", "detail.json"))
    completed = subprocess.run(
        [sys.executable, "-", str(csv_path), str(summary_path), str(md_path), str(detail_path)],
        input=helper, text=True, capture_output=True, check=True,
    )
    assert completed.returncode == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["attempt_count"] == 3
    assert summary["unique_scenario_count"] == 2
    assert summary["invalid_attempt_count"] == 2
    assert summary["invalid_configuration_count"] == 1
    assert summary["rerun_attempt_count"] == 1
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
    assert detail["aggregate_scoring_uses_latest_attempt"] is True
    assert len(detail["results"]) == 2
    assert detail["results"][0]["attempt_count"] == 2

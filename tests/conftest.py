from __future__ import annotations

import json
from pathlib import Path


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    reports = terminalreporter.stats
    regression_reports = [
        report
        for outcome in ("passed", "failed", "skipped", "error")
        for report in reports.get(outcome, [])
        if "test_payroll_rca_regression.py" in report.nodeid
    ]
    summary = {
        "exit_status": exitstatus,
        "scenario_count": 100,
        "regression_checks": len(regression_reports),
        "regression_passed": sum(report.passed for report in regression_reports),
        "regression_failed": sum(report.failed for report in regression_reports),
        "passed": len(reports.get("passed", [])),
        "failed": len(reports.get("failed", [])),
        "skipped": len(reports.get("skipped", [])),
    }
    target = Path("reports") / "payroll_rca_regression_summary.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

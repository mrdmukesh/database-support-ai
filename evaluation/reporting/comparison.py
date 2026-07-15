from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

DIMENSIONS = ("domain", "category", "difficulty", "release", "model_version", "judge_version")
METRICS = ("weighted_score", "confidence", "cost_usd", "duration_seconds")


def comparison_report(
    baseline: Iterable[dict[str, Any]], candidate: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    before, after = list(baseline), list(candidate)
    report = {
        "baseline": _summary(before),
        "candidate": _summary(after),
        "by_dimension": {},
    }
    for dimension in DIMENSIONS:
        baseline_groups = _groups(before, dimension)
        candidate_groups = _groups(after, dimension)
        report["by_dimension"][dimension] = {
            key: _compare(baseline_groups.get(key, []), candidate_groups.get(key, []))
            for key in sorted(set(baseline_groups) | set(candidate_groups))
        }
    report["top_failures"] = sorted(
        (row for row in after if row.get("failed") or float(row.get("weighted_score", 0)) <= 70),
        key=lambda row: float(row.get("weighted_score", 0)),
    )[:10]
    report["regressions"] = [
        row for row in report["by_dimension"]["category"].values()
        if row["score_delta"] is not None and row["score_delta"] < -2
    ]
    return report


def _groups(rows: list[dict[str, Any]], dimension: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(dimension) or "unknown")].append(row)
    return grouped


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(rows), "failed": sum(bool(row.get("failed")) for row in rows)}
    for metric in METRICS:
        values = [float(row[metric]) for row in rows if row.get(metric) is not None]
        summary[f"average_{metric}"] = round(sum(values) / len(values), 4) if values else None
    return summary


def _compare(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    baseline, candidate = _summary(before), _summary(after)
    left, right = baseline["average_weighted_score"], candidate["average_weighted_score"]
    return {"baseline": baseline, "candidate": candidate, "score_delta": round(right-left, 4) if left is not None and right is not None else None}

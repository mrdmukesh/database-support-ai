from __future__ import annotations

import json
from pathlib import Path

from evaluation.agentic_benchmark.models import (
    BenchmarkManifestEntry,
    GroundTruthStatus,
    ProtectedGroundTruth,
)
from evaluation.agentic_benchmark.runner import truth_from_scenario
from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.scenario_loader import load_scenarios

DOMAINS = ("banking", "payroll", "orders", "shipping", "clinic")
DEFAULT_ROOT = Path("evaluation/agentic_benchmark")


def load_agentic_25(
    root: str | Path = DEFAULT_ROOT,
) -> tuple[
    tuple[BenchmarkManifestEntry, ...],
    dict[str, ProtectedGroundTruth],
    dict[str, ScenarioContract],
]:
    base = Path(root)
    manifest_payload = json.loads(
        (base / "manifest.json").read_text(encoding="utf-8")
    )
    review_payload = json.loads(
        (base / "ground-truth-review.json").read_text(encoding="utf-8")
    )
    scenarios = {
        scenario.scenario_id: scenario
        for domain in DOMAINS
        for scenario in load_scenarios(
            Path("evaluation_scenarios") / domain / "scenarios.json"
        )
    }
    manifest = tuple(
        BenchmarkManifestEntry(
            scenario_id=item["scenario_id"],
            database=item["database"],
            domain=item["domain"],
            question=scenarios[item["scenario_id"]].question,
        )
        for item in manifest_payload
    )
    # This is intentionally loaded only by the post-investigation scorer.
    ground_truth = {
        entry.scenario_id: truth_from_scenario(
            scenarios[entry.scenario_id],
            GroundTruthStatus(review_payload[entry.scenario_id]),
        )
        for entry in manifest
    }
    return manifest, ground_truth, scenarios

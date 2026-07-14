from __future__ import annotations

import json
from pathlib import Path

from evaluation.framework.contracts import ScenarioContract


def load_scenarios(path: str | Path) -> list[ScenarioContract]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("scenario file must contain a JSON array")
    return [ScenarioContract(**item) for item in payload]


def select_latest_active(scenarios: list[ScenarioContract]) -> list[ScenarioContract]:
    latest: dict[str, ScenarioContract] = {}
    for scenario in scenarios:
        if not scenario.active:
            continue
        current = latest.get(scenario.scenario_id)
        if current is None or scenario.scenario_version > current.scenario_version:
            latest[scenario.scenario_id] = scenario
    return sorted(latest.values(), key=lambda item: item.scenario_id)

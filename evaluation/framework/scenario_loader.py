from __future__ import annotations

import json
from pathlib import Path

from evaluation.framework.contracts import ScenarioContract


def load_scenarios(path: str | Path, exclude_categories=None, exclude_tags=None, include_deterministic: bool = False) -> list[ScenarioContract]:
    def _normalize_set(arg):
        if arg is None:
            return None
        if isinstance(arg, (set, list, tuple)):
            return set(arg)
        return {arg}

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("scenario file must contain a JSON array")
    # Backwards-compatible: support optional exclusion filters via
    # explicit keyword args. We primarily use category and tags
    # metadata to decide exclusion. By default we exclude deterministic
    # fixture scenarios (category 'deterministic_fixture' or tag
    # 'deterministic') so benchmark loaders and tests count the
    # canonical benchmark manifests (25 per domain) unless a caller
    # explicitly opts in via `include_deterministic=True`.
    exclude_categories = _normalize_set(exclude_categories)
    exclude_tags = _normalize_set(exclude_tags)
    if not include_deterministic:
        if exclude_categories is None:
            exclude_categories = {"deterministic_fixture"}
        else:
            exclude_categories = set(exclude_categories) | {"deterministic_fixture"}
        if exclude_tags is None:
            exclude_tags = {"deterministic"}
        else:
            exclude_tags = set(exclude_tags) | {"deterministic"}

    def _is_excluded(item: dict) -> bool:
        if exclude_categories and item.get("category") in exclude_categories:
            return True
        tags = item.get("tags") or []
        if exclude_tags and any(t in exclude_tags for t in tags):
            return True
        return False

    if exclude_categories or exclude_tags:
        payload = [item for item in payload if not _is_excluded(item)]

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

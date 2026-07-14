"""Research evaluation foundation, isolated from production investigation orchestration."""

from evaluation.framework.contracts import ScenarioContract
from evaluation.framework.scoring import calculate_score

__all__ = ["ScenarioContract", "calculate_score"]

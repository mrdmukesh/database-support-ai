from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_LLM_MODEL = "gpt-4.1-mini"
# Provider model identifiers are configuration data. This tuple documents the
# initial built-in capability profiles; it is not an authorization allowlist.
SUPPORTED_LLM_MODELS = ("gpt-4.1-mini", "gpt-5-mini", "gpt-5.1")
SUPPORTED_REASONING_EFFORTS = ("none", "low", "medium", "high")


@dataclass(frozen=True)
class ModelCapabilities:
    responses_api: bool
    structured_output: bool
    reasoning_effort: bool


def normalize_model_name(value: str | None) -> str | None:
    model = (value or "").strip()
    if not model:
        return None
    return model if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,159}", model) else None


def safe_model_selection(candidate: str | None, fallback: str | None) -> tuple[str, str | None]:
    selected = normalize_model_name(candidate)
    configured_fallback = normalize_model_name(fallback)
    return selected or configured_fallback or DEFAULT_LLM_MODEL, configured_fallback


def model_capabilities(model: str) -> ModelCapabilities:
    normalized = normalize_model_name(model)
    if normalized is None:
        raise ValueError("Invalid LLM model identifier")
    return ModelCapabilities(
        True,
        True,
        normalized.startswith(("gpt-5.1", "gpt-5-mini")),
    )


def normalize_reasoning_effort(value: str | None) -> str:
    effort = (value or "medium").strip().casefold()
    return effort if effort in SUPPORTED_REASONING_EFFORTS else "medium"


def build_reasoning_parameters(
    *, model: str, reasoning_effort: str, max_output_tokens: int
) -> tuple[dict[str, object], tuple[str, ...]]:
    capabilities = model_capabilities(model)
    parameters: dict[str, object] = {"max_output_tokens": max(1, max_output_tokens)}
    unsupported: list[str] = []
    if capabilities.reasoning_effort:
        parameters["reasoning"] = {"effort": normalize_reasoning_effort(reasoning_effort)}
    elif reasoning_effort:
        unsupported.append("reasoning_effort")
    return parameters, tuple(unsupported)

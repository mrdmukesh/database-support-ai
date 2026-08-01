from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib import error

from legacydb_copilot.config import Settings
from legacydb_copilot.services.llm_model_configuration import build_reasoning_parameters
from legacydb_copilot.services.llm_provider_client import (
    AuditedLLMProviderClient,
    ProviderRequest,
)


class JSONInvoker(Protocol):
    def invoke_json(self, provider_request: ProviderRequest) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ModelPreflightResult:
    passed: bool
    provider: str
    model: str
    endpoint: str
    structured_output_parsed: bool
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    error: str | None = None


def _response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    return "".join(
        str(content.get("text") or "")
        for item in response.get("output", [])
        if isinstance(item, dict)
        for content in item.get("content", [])
        if isinstance(content, dict)
    )


def _sanitized_error(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        return f"HTTPError({exc.code})"
    return type(exc).__name__


def run_model_access_preflight(
    settings: Settings | None = None,
    *,
    client: JSONInvoker | None = None,
) -> ModelPreflightResult:
    settings = settings or Settings.from_env()
    model = settings.selected_reasoning_model
    endpoint = f"{settings.openai_base_url}/responses"
    if settings.llm_provider != "openai":
        return ModelPreflightResult(
            False, settings.llm_provider, model, endpoint, False, 0, 0, 0.0,
            "unsupported_provider",
        )
    if not settings.openai_api_key:
        return ModelPreflightResult(
            False, settings.llm_provider, model, endpoint, False, 0, 0, 0.0,
            "missing_credentials",
        )
    parameters, _ = build_reasoning_parameters(
        model=model,
        reasoning_effort=settings.llm_reasoning_effort,
        max_output_tokens=min(settings.llm_max_output_tokens, 64),
    )
    body = {
        "model": model,
        "input": "Return exactly this JSON object: {\"preflight\":\"ok\"}",
        **parameters,
    }
    try:
        response = (client or AuditedLLMProviderClient()).invoke_json(
            ProviderRequest(
                provider=settings.llm_provider,
                model=model,
                endpoint=endpoint,
                api_key=settings.openai_api_key,
                body=body,
                timeout_seconds=settings.selected_provider_timeout_seconds,
                input_cost_per_million=settings.llm_input_cost_per_million,
                output_cost_per_million=settings.llm_output_cost_per_million,
            )
        )
        parsed = json.loads(_response_text(response))
        structured = parsed == {"preflight": "ok"}
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cost = (
            input_tokens * settings.llm_input_cost_per_million
            + output_tokens * settings.llm_output_cost_per_million
        ) / 1_000_000
        return ModelPreflightResult(
            structured, settings.llm_provider, model, endpoint, structured,
            input_tokens, output_tokens, cost,
            None if structured else "structured_output_mismatch",
        )
    except Exception as exc:
        return ModelPreflightResult(
            False, settings.llm_provider, model, endpoint, False, 0, 0, 0.0,
            _sanitized_error(exc),
        )


def main() -> int:
    result = run_model_access_preflight()
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

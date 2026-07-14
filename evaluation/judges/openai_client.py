from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from evaluation.judges.ai_judge import JudgeProviderResponse, JudgeTransientError


class OpenAIJudgeClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million

    def complete(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        model: str,
        temperature: float,
        timeout_seconds: float,
    ) -> JudgeProviderResponse:
        body = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
            "temperature": temperature,
            "max_output_tokens": 1800,
        }
        call = request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(call, timeout=timeout_seconds) as response:
                response_json = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 or 500 <= exc.code < 600:
                raise JudgeTransientError(f"Judge HTTP {exc.code}: {detail}") from exc
            raise RuntimeError(f"Judge HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise JudgeTransientError(f"Judge request failed: {exc}") from exc
        usage = response_json.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cost = (
            input_tokens * self.input_cost_per_million
            + output_tokens * self.output_cost_per_million
        ) / 1_000_000
        return JudgeProviderResponse(
            raw_text=_response_text(response_json),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
        )


def _response_text(response_json: dict[str, Any]) -> str:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]
    chunks = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks)

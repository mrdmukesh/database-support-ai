from __future__ import annotations

import json
from collections.abc import Callable
from urllib import error, request

from evaluation.runners.contracts import TransientAPIError


class PublicInvestigationAPI:
    """Authenticated adapter for the same routes used by the React investigation client."""

    def __init__(self, base_url: str, access_token: str = "", *, token_provider: Callable[[], str] | None = None, request_timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.token_provider = token_provider
        self.request_timeout = request_timeout

    def submit(self, payload: dict) -> tuple[dict, int]:
        return self._request("POST", "/chat/ask", payload)

    def retrieve(self, investigation_id: str) -> tuple[dict, int]:
        return self._request("GET", f"/learning/investigations/{investigation_id}")

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[dict, int]:
        return self._request_once(method, path, payload, allow_refresh=True)

    def _request_once(self, method: str, path: str, payload: dict | None, *, allow_refresh: bool) -> tuple[dict, int]:
        if not self.access_token and self.token_provider is not None:
            self.access_token = self.token_provider()
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        call = request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with request.urlopen(call, timeout=self.request_timeout) as response:
                return json.loads(response.read().decode("utf-8")), response.status
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401 and allow_refresh and self.token_provider is not None:
                self.access_token = self.token_provider()
                return self._request_once(method, path, payload, allow_refresh=False)
            if exc.code == 429 or 500 <= exc.code < 600:
                raise TransientAPIError(f"HTTP {exc.code}: {detail}") from exc
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise TransientAPIError(f"API network failure: {exc}") from exc


class EvaluationServiceTokenProvider:
    def __init__(self, base_url: str, client_id: str, client_secret: str, *, request_timeout: float = 30.0):
        self.url = base_url.rstrip("/") + "/auth/evaluation-token"
        self.client_id = client_id
        self.client_secret = client_secret
        self.request_timeout = request_timeout

    def __call__(self) -> str:
        body = json.dumps({"client_id": self.client_id, "client_secret": self.client_secret}).encode("utf-8")
        call = request.Request(self.url, data=body, headers={"Accept": "application/json", "Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(call, timeout=self.request_timeout) as response:
                token = json.loads(response.read().decode("utf-8")).get("access_token")
                if not token:
                    raise RuntimeError("Evaluation token response did not include an access token")
                return str(token)
        except error.HTTPError as exc:
            raise RuntimeError(f"Evaluation service authentication failed with HTTP {exc.code}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise TransientAPIError(f"Evaluation service authentication network failure: {exc}") from exc

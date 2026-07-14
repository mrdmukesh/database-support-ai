from __future__ import annotations

import json
from urllib import error, request

from evaluation.runners.contracts import TransientAPIError


class PublicInvestigationAPI:
    """Authenticated adapter for the same routes used by the React investigation client."""

    def __init__(self, base_url: str, access_token: str, *, request_timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.request_timeout = request_timeout

    def submit(self, payload: dict) -> tuple[dict, int]:
        return self._request("POST", "/chat/ask", payload)

    def retrieve(self, investigation_id: str) -> tuple[dict, int]:
        return self._request("GET", f"/learning/investigations/{investigation_id}")

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[dict, int]:
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
            if exc.code == 429 or 500 <= exc.code < 600:
                raise TransientAPIError(f"HTTP {exc.code}: {detail}") from exc
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise TransientAPIError(f"API network failure: {exc}") from exc

from typing import Any

import requests
from requests import HTTPError


class MissingOddsPapiKeyError(RuntimeError):
    pass


class OddsPapiRequestBudgetExceededError(RuntimeError):
    pass


class OddsPapiApiError(RuntimeError):
    pass


class OddsPapiClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_seconds: int = 20,
        request_budget: int = 50,
        session: Any | None = None,
    ) -> None:
        if not api_key:
            raise MissingOddsPapiKeyError("ODDSPAPI_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_budget = request_budget
        self.session = session or requests.Session()
        self.request_count = 0

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        if self.request_count >= self.request_budget:
            raise OddsPapiRequestBudgetExceededError("OddsPapi request budget exceeded")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = dict(params or {})
        request_params["apiKey"] = self.api_key
        response = self.session.get(
            url,
            params=request_params,
            timeout=self.timeout_seconds,
        )
        self.request_count += 1
        try:
            response.raise_for_status()
        except HTTPError as exc:
            status_code = getattr(exc.response, "status_code", "unknown")
            raise OddsPapiApiError(f"OddsPapi HTTP error: status={status_code}") from exc
        except Exception as exc:
            raise OddsPapiApiError(
                f"OddsPapi HTTP error: {exc.__class__.__name__}"
            ) from exc
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise OddsPapiApiError(f"OddsPapi returned error: {payload['error']}")
        return payload

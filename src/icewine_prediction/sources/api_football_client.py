from typing import Any

import requests
from requests import HTTPError


class MissingApiKeyError(RuntimeError):
    pass


class RequestBudgetExceededError(RuntimeError):
    pass


class ApiFootballApiError(RuntimeError):
    pass


class ApiFootballClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_seconds: int = 20,
        daily_request_budget: int = 100,
        session: Any | None = None,
    ) -> None:
        if not api_key:
            raise MissingApiKeyError("API_FOOTBALL_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.daily_request_budget = daily_request_budget
        self.session = session or requests.Session()
        self.request_count = 0

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.request_count >= self.daily_request_budget:
            raise RequestBudgetExceededError("API-Football request budget exceeded")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(
            url,
            headers={"x-apisports-key": self.api_key},
            params=params or {},
            timeout=self.timeout_seconds,
        )
        self.request_count += 1
        try:
            response.raise_for_status()
        except HTTPError as exc:
            status_code = getattr(response, "status_code", "unknown")
            raise ApiFootballApiError(f"API-Football HTTP error {status_code}: {exc}") from exc
        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise ApiFootballApiError(f"API-Football returned errors: {errors}")
        return payload

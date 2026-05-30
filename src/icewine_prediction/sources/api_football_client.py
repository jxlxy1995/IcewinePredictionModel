from typing import Any
from time import sleep as default_sleep

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
        request_cooldown_seconds: float = 0.0,
        max_retries: int = 0,
        retry_cooldown_seconds: float = 0.0,
        sleep: Any = default_sleep,
    ) -> None:
        if not api_key:
            raise MissingApiKeyError("API_FOOTBALL_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.daily_request_budget = daily_request_budget
        self.session = session or requests.Session()
        self.request_cooldown_seconds = request_cooldown_seconds
        self.max_retries = max_retries
        self.retry_cooldown_seconds = retry_cooldown_seconds
        self.sleep = sleep
        self.request_count = 0

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        attempts = self.max_retries + 1
        for attempt_index in range(attempts):
            try:
                response = self._send_get(url, params or {})
                break
            except requests.RequestException as exc:
                if attempt_index >= self.max_retries:
                    raise ApiFootballApiError(f"API-Football request failed: {exc}") from exc
                if self.retry_cooldown_seconds > 0:
                    self.sleep(self.retry_cooldown_seconds)
        else:
            raise ApiFootballApiError("API-Football request failed")
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

    def _send_get(self, url: str, params: dict[str, Any]) -> Any:
        if self.request_count >= self.daily_request_budget:
            raise RequestBudgetExceededError("API-Football request budget exceeded")
        if self.request_count > 0 and self.request_cooldown_seconds > 0:
            self.sleep(self.request_cooldown_seconds)
        try:
            return self.session.get(
                url,
                headers={"x-apisports-key": self.api_key},
                params=params,
                timeout=self.timeout_seconds,
            )
        finally:
            self.request_count += 1

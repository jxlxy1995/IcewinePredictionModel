from typing import Any

import requests


THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"


class MissingTheOddsApiKeyError(RuntimeError):
    pass


class TheOddsApiRequestBudgetExceededError(RuntimeError):
    pass


class TheOddsApiApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TheOddsApiClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = THE_ODDS_API_BASE_URL,
        timeout_seconds: int = 20,
        request_budget: int = 20,
        session: Any | None = None,
    ) -> None:
        if not api_key:
            raise MissingTheOddsApiKeyError("THE_ODDS_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_budget = request_budget
        self.session = session or _build_default_session()
        self.request_count = 0
        self.credit_count = 0
        self.last_credit_count = 0
        self.provider_requests_used: int | None = None
        self.provider_requests_remaining: int | None = None

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        if self.request_count >= self.request_budget:
            raise TheOddsApiRequestBudgetExceededError("The Odds API request budget exceeded")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = dict(params or {})
        request_params["apiKey"] = self.api_key
        self.request_count += 1
        try:
            response = self.session.get(
                url,
                params=request_params,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise TheOddsApiApiError(
                f"The Odds API request failed: {exc.__class__.__name__}"
            ) from None
        try:
            response.raise_for_status()
        except Exception as exc:
            status_code = getattr(response, "status_code", None)
            provider_message = _response_error_message(response)
            details = [f"The Odds API HTTP error: {exc.__class__.__name__}"]
            if isinstance(status_code, int):
                details.append(f"status={status_code}")
            if provider_message:
                details.append(provider_message)
            raise TheOddsApiApiError(
                "; ".join(details),
                status_code=status_code if isinstance(status_code, int) else None,
            ) from None
        payload = response.json()
        self._record_credit_headers(response)
        if isinstance(payload, dict) and payload.get("message"):
            raise TheOddsApiApiError(f"The Odds API returned error: {payload['message']}")
        return payload

    def reset_session(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()
        self.session = _build_default_session()

    def _record_credit_headers(self, response: Any) -> None:
        headers = getattr(response, "headers", {}) or {}
        last = _int_header(headers, "x-requests-last")
        if last is not None:
            self.last_credit_count = last
            self.credit_count += last
        used = _int_header(headers, "x-requests-used")
        if used is not None:
            self.provider_requests_used = used
        remaining = _int_header(headers, "x-requests-remaining")
        if remaining is not None:
            self.provider_requests_remaining = remaining


def _build_default_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _response_error_message(response: Any) -> str | None:
    try:
        payload = response.json()
    except Exception:
        return None
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if message:
            return str(message)
    return None


def _int_header(headers: Any, name: str) -> int | None:
    value = None
    if hasattr(headers, "get"):
        value = headers.get(name) or headers.get(name.upper())
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

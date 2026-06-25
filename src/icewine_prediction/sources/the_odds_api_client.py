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
            raise TheOddsApiApiError(
                f"The Odds API HTTP error: {exc.__class__.__name__}",
                status_code=status_code if isinstance(status_code, int) else None,
            ) from None
        payload = response.json()
        if isinstance(payload, dict) and payload.get("message"):
            raise TheOddsApiApiError(f"The Odds API returned error: {payload['message']}")
        return payload

    def reset_session(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()
        self.session = _build_default_session()


def _build_default_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session

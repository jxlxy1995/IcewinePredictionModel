import time
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from typing import Any, Callable

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


class TheOddsApiExtraTimeBudgetExceededError(RuntimeError):
    pass


@dataclass
class TheOddsApiRecoveryBudget:
    limit_seconds: float = 120.0
    limiter_wait_seconds: float = 0.0
    backoff_wait_seconds: float = 0.0
    retry_elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "limit_seconds",
            "limiter_wait_seconds",
            "backoff_wait_seconds",
            "retry_elapsed_seconds",
        ):
            value = getattr(self, field_name)
            if value < 0.0 or not isfinite(value):
                raise ValueError(f"{field_name} must be finite and non-negative")

    @property
    def consumed_seconds(self) -> float:
        return (
            self.limiter_wait_seconds
            + self.backoff_wait_seconds
            + self.retry_elapsed_seconds
        )

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.limit_seconds - self.consumed_seconds)

    def require_capacity(self, seconds: float) -> None:
        required_seconds = max(0.0, seconds)
        if required_seconds > self.remaining_seconds:
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API recovery time budget exceeded"
            )

    def add_limiter_wait(self, seconds: float) -> None:
        wait_seconds = max(0.0, seconds)
        self.require_capacity(wait_seconds)
        self.limiter_wait_seconds += wait_seconds

    def add_backoff_wait(self, seconds: float) -> None:
        wait_seconds = max(0.0, seconds)
        self.require_capacity(wait_seconds)
        self.backoff_wait_seconds += wait_seconds

    def add_retry_elapsed(self, seconds: float) -> None:
        elapsed_seconds = max(0.0, seconds)
        self.require_capacity(elapsed_seconds)
        self.retry_elapsed_seconds += elapsed_seconds


class TheOddsApiRequestLimiter:
    def __init__(
        self,
        cooldown_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._lock = Lock()

    def wait(self, budget: TheOddsApiRecoveryBudget) -> float:
        lock_wait_started_at: float | None = None
        if self._lock.acquire(blocking=False):
            lock_wait_seconds = 0.0
        else:
            lock_wait_started_at = self._clock()
            lock_timeout = budget.remaining_seconds
            if not self._lock.acquire(timeout=lock_timeout):
                lock_wait_seconds = max(
                    lock_timeout,
                    self._clock() - lock_wait_started_at,
                )
                self._charge_limiter_wait(budget, lock_wait_seconds)
                raise TheOddsApiExtraTimeBudgetExceededError(
                    "The Odds API recovery time budget exceeded"
                )

        try:
            lock_acquired_at = self._clock()
            if lock_wait_started_at is not None:
                lock_wait_seconds = max(
                    0.0,
                    lock_acquired_at - lock_wait_started_at,
                )
            self._charge_limiter_wait(budget, lock_wait_seconds)

            required_wait_seconds = 0.0
            if self._last_request_at is not None:
                elapsed_since_request = lock_acquired_at - self._last_request_at
                required_wait_seconds = max(
                    0.0,
                    self.cooldown_seconds - elapsed_since_request,
                )
            budget.require_capacity(required_wait_seconds)
            request_permitted_at = lock_acquired_at
            pacing_wait_seconds = 0.0
            if required_wait_seconds > 0.0:
                pacing_wait_started_at = self._clock()
                self._sleeper(required_wait_seconds)
                request_permitted_at = self._clock()
                pacing_wait_seconds = max(
                    0.0,
                    request_permitted_at - pacing_wait_started_at,
                )
            self._charge_limiter_wait(budget, pacing_wait_seconds)
            self._last_request_at = request_permitted_at
            return lock_wait_seconds + pacing_wait_seconds
        finally:
            self._lock.release()

    @staticmethod
    def _charge_limiter_wait(
        budget: TheOddsApiRecoveryBudget,
        seconds: float,
    ) -> None:
        wait_seconds = max(0.0, seconds)
        remaining_seconds = budget.remaining_seconds
        if wait_seconds > remaining_seconds:
            budget.limiter_wait_seconds += wait_seconds
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API recovery time budget exceeded"
            )
        budget.add_limiter_wait(wait_seconds)


GLOBAL_THE_ODDS_API_REQUEST_LIMITER = TheOddsApiRequestLimiter()


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

import logging
import time
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from typing import Any, Callable

import requests


THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
logger = logging.getLogger(__name__)


class MissingTheOddsApiKeyError(RuntimeError):
    pass


class TheOddsApiRequestBudgetExceededError(RuntimeError):
    pass


class TheOddsApiApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        error_code: str = "request_error",
        retry_after_seconds: float | None = None,
        attempt_count: int = 1,
        retry_exhausted: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds
        self.attempt_count = attempt_count
        self.retry_exhausted = retry_exhausted


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
        request_limiter: TheOddsApiRequestLimiter | None = None,
        recovery_budget: TheOddsApiRecoveryBudget | None = None,
        max_retries: int = 1,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        trace_id: str | None = None,
    ) -> None:
        if not api_key:
            raise MissingTheOddsApiKeyError("THE_ODDS_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_budget = request_budget
        self.session = session or _build_default_session()
        self.request_limiter = request_limiter or GLOBAL_THE_ODDS_API_REQUEST_LIMITER
        self.recovery_budget = recovery_budget or TheOddsApiRecoveryBudget()
        self.max_retries = max(0, max_retries)
        self._clock = clock
        self._sleeper = sleeper
        self.trace_id = trace_id
        self.request_count = 0
        self.retry_count = 0
        self.retry_success_count = 0
        self.last_request_attempt_count = 0
        self.credit_count = 0
        self.last_credit_count = 0
        self.provider_requests_used: int | None = None
        self.provider_requests_remaining: int | None = None

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = dict(params or {})
        request_params["apiKey"] = self.api_key
        safe_metadata = _safe_request_metadata(request_params)

        for attempt in range(1, self.max_retries + 2):
            try:
                limiter_wait = self.request_limiter.wait(self.recovery_budget)
            except TheOddsApiExtraTimeBudgetExceededError:
                self.last_request_attempt_count = attempt
                raise self._retry_budget_error(attempt) from None

            started = self._clock()
            try:
                payload = self._request_once(url, request_params)
            except TheOddsApiApiError as error:
                elapsed = max(0.0, self._clock() - started)
                if attempt > 1:
                    try:
                        self._charge_retry_elapsed(elapsed)
                    except TheOddsApiExtraTimeBudgetExceededError:
                        self.last_request_attempt_count = attempt
                        raise self._retry_budget_error(attempt) from None
                error.attempt_count = attempt
                self.last_request_attempt_count = attempt
                retry_delay = self._retry_delay(error)
                if retry_delay is None:
                    error.retry_exhausted = False
                    raise
                if attempt >= self.max_retries + 1:
                    error.retry_exhausted = True
                    raise
                try:
                    actual_backoff = self._sleep_for_retry(retry_delay)
                except TheOddsApiExtraTimeBudgetExceededError:
                    raise self._retry_budget_error(attempt) from None
                self.retry_count += 1
                logger.warning(
                    "The Odds API retry trace_id=%s endpoint=%s attempt=%s "
                    "error_code=%s limiter_wait=%s backoff=%s",
                    self.trace_id,
                    endpoint,
                    attempt,
                    error.error_code,
                    limiter_wait,
                    actual_backoff,
                    extra={
                        "trace_id": self.trace_id,
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "error_code": error.error_code,
                        "limiter_wait": limiter_wait,
                        "backoff": actual_backoff,
                    },
                )
                continue

            elapsed = max(0.0, self._clock() - started)
            if attempt > 1:
                try:
                    self._charge_retry_elapsed(elapsed)
                except TheOddsApiExtraTimeBudgetExceededError:
                    self.last_request_attempt_count = attempt
                    raise self._retry_budget_error(attempt) from None
                self.retry_success_count += 1
            self.last_request_attempt_count = attempt
            logger.info(
                "The Odds API request succeeded trace_id=%s endpoint=%s "
                "attempt=%s elapsed=%s metadata=%s",
                self.trace_id,
                endpoint,
                attempt,
                elapsed,
                safe_metadata,
                extra={
                    "trace_id": self.trace_id,
                    "endpoint": endpoint,
                    "attempt": attempt,
                    "elapsed": elapsed,
                    **safe_metadata,
                },
            )
            return payload

        raise AssertionError("unreachable")

    def _request_once(self, url: str, request_params: dict[str, Any]) -> Any:
        if self.request_count >= self.request_budget:
            raise TheOddsApiRequestBudgetExceededError(
                "The Odds API request budget exceeded"
            )
        self.request_count += 1
        try:
            response = self.session.get(
                url,
                params=request_params,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.ReadTimeout:
            raise TheOddsApiApiError(
                "The Odds API request timed out",
                error_code="read_timeout",
            ) from None
        except requests.exceptions.ConnectionError as exc:
            raise TheOddsApiApiError(
                f"The Odds API connection failed: {exc.__class__.__name__}",
                error_code="connection_error",
            ) from None
        except requests.RequestException as exc:
            raise TheOddsApiApiError(
                f"The Odds API request failed: {exc.__class__.__name__}",
                error_code="request_error",
            ) from None
        try:
            response.raise_for_status()
        except Exception:
            status_code = getattr(response, "status_code", None)
            provider_message = _response_error_message(response)
            details = ["The Odds API HTTP error"]
            if isinstance(status_code, int):
                details.append(f"status={status_code}")
            if provider_message:
                details.append(provider_message)
            raise TheOddsApiApiError(
                "; ".join(details),
                status_code=status_code if isinstance(status_code, int) else None,
                error_code=(
                    f"http_{status_code}" if isinstance(status_code, int) else "http_error"
                ),
                retry_after_seconds=_retry_after_seconds(
                    getattr(response, "headers", {}) or {}
                ),
            ) from None
        payload = response.json()
        self._record_credit_headers(response)
        if isinstance(payload, dict) and payload.get("message"):
            raise TheOddsApiApiError(
                f"The Odds API returned error: {payload['message']}",
                error_code="provider_error",
            )
        return payload

    @staticmethod
    def _retry_delay(error: TheOddsApiApiError) -> float | None:
        if error.error_code in {"read_timeout", "connection_error"}:
            return 5.0
        if error.status_code == 429:
            if error.retry_after_seconds is not None:
                return error.retry_after_seconds
            return 15.0
        if error.status_code in {500, 502, 503, 504}:
            return 5.0
        return None

    def _sleep_for_retry(self, seconds: float) -> float:
        self.recovery_budget.require_capacity(seconds + self.timeout_seconds)
        started = self._clock()
        self._sleeper(seconds)
        actual_seconds = max(0.0, self._clock() - started)
        remaining_seconds = self.recovery_budget.remaining_seconds
        if actual_seconds > remaining_seconds:
            self.recovery_budget.backoff_wait_seconds += actual_seconds
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API recovery time budget exceeded"
            )
        self.recovery_budget.add_backoff_wait(actual_seconds)
        self.recovery_budget.require_capacity(self.timeout_seconds)
        return actual_seconds

    def _charge_retry_elapsed(self, seconds: float) -> None:
        elapsed_seconds = max(0.0, seconds)
        if elapsed_seconds > self.recovery_budget.remaining_seconds:
            self.recovery_budget.retry_elapsed_seconds += elapsed_seconds
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API recovery time budget exceeded"
            )
        self.recovery_budget.add_retry_elapsed(elapsed_seconds)

    @staticmethod
    def _retry_budget_error(attempt: int) -> TheOddsApiApiError:
        return TheOddsApiApiError(
            "The Odds API retry budget exhausted",
            error_code="retry_budget_exhausted",
            attempt_count=attempt,
            retry_exhausted=True,
        )

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


def _retry_after_seconds(headers: Any) -> float | None:
    value = None
    if hasattr(headers, "get"):
        for name in ("Retry-After", "retry-after", "RETRY-AFTER"):
            value = headers.get(name)
            if value is not None:
                break
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0.0 or not isfinite(seconds):
        return None
    return seconds


def _safe_request_metadata(params: dict[str, Any]) -> dict[str, Any]:
    allowed_names = {"regions", "bookmakers", "markets", "dateFormat", "date"}
    scalar_types = (str, int, float, bool)
    return {
        name: value
        for name, value in params.items()
        if name in allowed_names and isinstance(value, scalar_types)
    }


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

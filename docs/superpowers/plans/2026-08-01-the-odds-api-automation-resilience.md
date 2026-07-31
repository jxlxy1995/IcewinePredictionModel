# The Odds API Automation Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make The Odds API automation tolerate transient request failures without aborting a multi-match task, while enforcing process-wide pacing and a 120-second added-time budget.

**Architecture:** Add request-control primitives and retry behavior to `TheOddsApiClient`, pass one recovery budget and trace ID through the unified match sync, and make the runner return per-match outcomes instead of one batch error. Preserve the existing fallback order and response keys, then enrich automation summaries with retry, not-attempted, and old-odds fallback counts.

**Tech Stack:** Python 3.11, `requests`, SQLAlchemy, pytest, standard-library dataclasses/threading/logging/time/uuid.

---

## Execution Preconditions

- Read `Agent.md` before execution.
- Use `C:\ProgramData\anaconda3\python.exe` and set `PYTHONPATH=src`, `PYTHONIOENCODING=utf-8`.
- Create an isolated worktree from commit `2d74791` with the `using-git-worktrees` skill before changing production code.
- Do not include the existing user change in `config/display_names.yaml` in any commit.
- Reference design: `docs/superpowers/specs/2026-08-01-the-odds-api-automation-resilience-design.md`.
- All commit messages below are Chinese, as required by the repository.

## File Map

- Modify `src/icewine_prediction/sources/the_odds_api_client.py`: recovery budget, process-wide limiter, typed errors, retry policy, request telemetry, and redacted logs.
- Modify `src/icewine_prediction/the_odds_api_sync_runner.py`: per-request success/failure cache, partial historical coverage, per-match outcomes, trace and recovery statistics.
- Modify `src/icewine_prediction/match_odds_sync_service.py`: create one trace/budget per unified sync, share them across seasons, and merge primary/fallback results accurately.
- Modify `src/icewine_prediction/paper_automation_service.py`: format richer odds summaries without changing task state semantics.
- Modify `tests/test_the_odds_api_client.py`: deterministic limiter, retry, budget, error classification, and secret-redaction tests.
- Modify `tests/test_the_odds_api_sync_runner.py`: shared failure cache, partial success, and multi-match isolation tests.
- Modify `tests/test_match_odds_sync_service.py`: cross-season budget propagation and final per-match classification tests.
- Modify `tests/test_paper_automation_service.py`: Bark summary and backward-compatibility tests.

### Task 1: Add Recovery Budget And Process-Wide Limiter

**Files:**
- Modify: `src/icewine_prediction/sources/the_odds_api_client.py:1-44`
- Test: `tests/test_the_odds_api_client.py`

- [ ] **Step 1: Write failing budget and limiter tests**

Add these imports and deterministic clock to `tests/test_the_odds_api_client.py`:

```python
from icewine_prediction.sources.the_odds_api_client import (
    MissingTheOddsApiKeyError,
    TheOddsApiApiError,
    TheOddsApiClient,
    TheOddsApiExtraTimeBudgetExceededError,
    TheOddsApiRecoveryBudget,
    TheOddsApiRequestBudgetExceededError,
    TheOddsApiRequestLimiter,
)


class FakeTime:
    def __init__(self, now: float = 100.0):
        self.now = now
        self.sleeps = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
```

Add these tests:

```python
def test_the_odds_api_request_limiter_charges_only_required_wait():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert limiter.wait(budget) == 0.0
    fake_time.now += 0.25
    assert limiter.wait(budget) == pytest.approx(0.75)

    assert fake_time.sleeps == [pytest.approx(0.75)]
    assert budget.limiter_wait_seconds == pytest.approx(0.75)
    assert budget.remaining_seconds == pytest.approx(119.25)


def test_the_odds_api_request_limiter_refuses_wait_beyond_budget():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget(limit_seconds=0.5)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    limiter.wait(budget)
    with pytest.raises(TheOddsApiExtraTimeBudgetExceededError):
        limiter.wait(budget)

    assert fake_time.sleeps == []
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_client.py::test_the_odds_api_request_limiter_charges_only_required_wait tests\test_the_odds_api_client.py::test_the_odds_api_request_limiter_refuses_wait_beyond_budget -q
```

Expected: collection fails because the three new request-control types do not exist.

- [ ] **Step 3: Implement the budget and limiter primitives**

Add imports to `src/icewine_prediction/sources/the_odds_api_client.py`:

```python
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable
```

Add these types before `TheOddsApiClient`:

```python
class TheOddsApiExtraTimeBudgetExceededError(RuntimeError):
    pass


@dataclass
class TheOddsApiRecoveryBudget:
    limit_seconds: float = 120.0
    limiter_wait_seconds: float = 0.0
    backoff_wait_seconds: float = 0.0
    retry_elapsed_seconds: float = 0.0

    @property
    def consumed_seconds(self) -> float:
        return self.limiter_wait_seconds + self.backoff_wait_seconds + self.retry_elapsed_seconds

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.limit_seconds - self.consumed_seconds)

    def require_capacity(self, seconds: float) -> None:
        if max(0.0, seconds) > self.remaining_seconds:
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API extra-time budget exhausted"
            )

    def add_limiter_wait(self, seconds: float) -> None:
        self.require_capacity(seconds)
        self.limiter_wait_seconds += max(0.0, seconds)

    def add_backoff_wait(self, seconds: float) -> None:
        self.require_capacity(seconds)
        self.backoff_wait_seconds += max(0.0, seconds)

    def add_retry_elapsed(self, seconds: float) -> None:
        self.require_capacity(seconds)
        self.retry_elapsed_seconds += max(0.0, seconds)


class TheOddsApiRequestLimiter:
    def __init__(
        self,
        cooldown_seconds: float = 1.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.clock = clock
        self.sleeper = sleeper
        self._last_request_at = 0.0
        self._lock = Lock()

    def wait(self, budget: TheOddsApiRecoveryBudget) -> float:
        with self._lock:
            now = self.clock()
            elapsed = now - self._last_request_at
            wait_seconds = 0.0
            if self._last_request_at > 0 and elapsed < self.cooldown_seconds:
                wait_seconds = self.cooldown_seconds - elapsed
            budget.require_capacity(wait_seconds)
            if wait_seconds > 0:
                self.sleeper(wait_seconds)
                budget.add_limiter_wait(wait_seconds)
            self._last_request_at = self.clock()
            return wait_seconds


GLOBAL_THE_ODDS_API_REQUEST_LIMITER = TheOddsApiRequestLimiter()
```

- [ ] **Step 4: Run client tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_client.py -q
```

Expected: all client tests pass, including the two new limiter tests.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/icewine_prediction/sources/the_odds_api_client.py tests/test_the_odds_api_client.py
git commit -m "增加The Odds API请求限速预算"
```

### Task 2: Add Typed Retry Policy And Redacted Request Logs

**Files:**
- Modify: `src/icewine_prediction/sources/the_odds_api_client.py:17-105`
- Test: `tests/test_the_odds_api_client.py`

- [ ] **Step 1: Make the fake session support exceptions**

Replace `FakeSession.get` in `tests/test_the_odds_api_client.py` with:

```python
def get(self, url, params, timeout):
    self.calls.append((url, params, timeout))
    response = self.responses.pop(0)
    if isinstance(response, BaseException):
        raise response
    return response
```

- [ ] **Step 2: Write failing retry, classification, budget, and redaction tests**

Add a helper that disables real waiting while preserving budget accounting:

```python
def _controlled_client(*, responses, timeout_seconds=40, recovery_limit=120.0):
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget(limit_seconds=recovery_limit)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=timeout_seconds,
        request_budget=20,
        session=FakeSession(responses),
        request_limiter=limiter,
        recovery_budget=budget,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
        trace_id="trace-test",
    )
    return client, fake_time, budget
```

Add `_no_wait_limiter()` and pass it to every pre-existing direct `TheOddsApiClient` construction in this test module so the new production default does not introduce real sleeps:

```python
def _no_wait_limiter() -> TheOddsApiRequestLimiter:
    return TheOddsApiRequestLimiter(cooldown_seconds=0.0)
```

Each existing construction uses `request_limiter=_no_wait_limiter()`. Existing tests whose only purpose is error wrapping or redaction also use `max_retries=0`; retry behavior is covered by the new controlled tests.

Add these tests:

```python
def test_the_odds_api_client_retries_read_timeout_once():
    client, fake_time, budget = _controlled_client(
        responses=[requests.ReadTimeout("slow"), FakeResponse({"ok": True})]
    )

    assert client.get("sports/soccer_epl/odds") == {"ok": True}
    assert client.request_count == 2
    assert client.retry_count == 1
    assert client.retry_success_count == 1
    assert budget.backoff_wait_seconds == pytest.approx(5.0)
    assert fake_time.sleeps == [pytest.approx(5.0)]


def test_the_odds_api_client_uses_retry_after_for_429():
    client, fake_time, budget = _controlled_client(
        responses=[
            FakeResponse({}, status_code=429, headers={"Retry-After": "12"}),
            FakeResponse({"ok": True}),
        ]
    )

    assert client.get("sports/soccer_epl/odds") == {"ok": True}
    assert budget.backoff_wait_seconds == pytest.approx(12.0)
    assert fake_time.sleeps == [pytest.approx(12.0)]


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_the_odds_api_client_retries_selected_server_errors(status_code):
    client, fake_time, _budget = _controlled_client(
        responses=[FakeResponse({}, status_code=status_code), FakeResponse({"ok": True})]
    )

    assert client.get("sports/soccer_epl/odds") == {"ok": True}
    assert client.request_count == 2
    assert fake_time.sleeps == [pytest.approx(5.0)]


def test_the_odds_api_client_retries_connection_error_once():
    client, fake_time, _budget = _controlled_client(
        responses=[requests.ConnectionError("offline"), FakeResponse({"ok": True})]
    )

    assert client.get("sports/soccer_epl/odds") == {"ok": True}
    assert client.request_count == 2
    assert fake_time.sleeps == [pytest.approx(5.0)]


@pytest.mark.parametrize("retry_after", [None, "invalid", "-1"])
def test_the_odds_api_client_uses_default_backoff_for_invalid_retry_after(retry_after):
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    client, fake_time, _budget = _controlled_client(
        responses=[FakeResponse({}, status_code=429, headers=headers), FakeResponse({"ok": True})]
    )

    assert client.get("sports/soccer_epl/odds") == {"ok": True}
    assert fake_time.sleeps == [pytest.approx(15.0)]


@pytest.mark.parametrize("status_code", [401, 403, 422])
def test_the_odds_api_client_does_not_retry_non_retryable_client_errors(status_code):
    client, fake_time, _budget = _controlled_client(
        responses=[FakeResponse({"message": "bad request"}, status_code=status_code)]
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports/soccer_epl/odds")

    assert exc_info.value.error_code == f"http_{status_code}"
    assert client.request_count == 1
    assert fake_time.sleeps == []


def test_the_odds_api_client_skips_retry_when_budget_cannot_cover_timeout():
    client, fake_time, _budget = _controlled_client(
        responses=[requests.ReadTimeout("slow")],
        timeout_seconds=40,
        recovery_limit=44.0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports/soccer_epl/odds")

    assert exc_info.value.error_code == "retry_budget_exhausted"
    assert client.request_count == 1
    assert fake_time.sleeps == []


def test_the_odds_api_client_retry_log_redacts_api_key(caplog):
    client, _fake_time, _budget = _controlled_client(
        responses=[requests.ReadTimeout("https://example.test?apiKey=secret"), FakeResponse({})]
    )

    client.get("sports/soccer_epl/odds")

    assert "trace-test" in caplog.text
    assert "secret" not in caplog.text
    assert "apiKey" not in caplog.text


def test_the_odds_api_clients_can_share_one_process_limiter():
    fake_time = FakeTime()
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )
    first = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({})]),
        request_limiter=limiter,
        recovery_budget=TheOddsApiRecoveryBudget(),
        max_retries=0,
    )
    second = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({})]),
        request_limiter=limiter,
        recovery_budget=TheOddsApiRecoveryBudget(),
        max_retries=0,
    )

    first.get("sports/soccer_epl/odds")
    fake_time.now += 0.25
    second.get("sports/soccer_epl/odds")

    assert fake_time.sleeps == [pytest.approx(0.75)]
```

- [ ] **Step 3: Run the new retry tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_client.py -q
```

Expected: failures for new constructor arguments, error metadata, and retry counters.

- [ ] **Step 4: Extend the API error and client constructor**

Use this error contract:

```python
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
```

Extend `TheOddsApiClient.__init__` with injectable controls and counters:

```python
self.request_limiter = request_limiter or GLOBAL_THE_ODDS_API_REQUEST_LIMITER
self.recovery_budget = recovery_budget or TheOddsApiRecoveryBudget()
self.max_retries = max(0, max_retries)
self.clock = clock
self.sleeper = sleeper
self.trace_id = trace_id
self.retry_count = 0
self.retry_success_count = 0
self.last_request_attempt_count = 0
```

The new constructor parameters are:

```python
request_limiter: TheOddsApiRequestLimiter | None = None,
recovery_budget: TheOddsApiRecoveryBudget | None = None,
max_retries: int = 1,
clock: Callable[[], float] = time.monotonic,
sleeper: Callable[[float], None] = time.sleep,
trace_id: str | None = None,
```

- [ ] **Step 5: Split one HTTP attempt from retry orchestration**

Add these helpers to `TheOddsApiClient`:

```python
def _retry_delay(self, error: TheOddsApiApiError) -> float | None:
    if error.error_code in {"read_timeout", "connection_error"}:
        return 5.0
    if error.status_code == 429:
        return error.retry_after_seconds if error.retry_after_seconds is not None else 15.0
    if error.status_code in {500, 502, 503, 504}:
        return 5.0
    return None

def _sleep_for_retry(self, seconds: float) -> None:
    self.recovery_budget.require_capacity(seconds + self.timeout_seconds)
    if seconds > 0:
        self.sleeper(seconds)
        self.recovery_budget.add_backoff_wait(seconds)

def _request_once(self, endpoint: str, request_params: dict[str, Any]) -> Any:
    if self.request_count >= self.request_budget:
        raise TheOddsApiRequestBudgetExceededError("The Odds API request budget exceeded")
    self.request_count += 1
    try:
        response = self.session.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            params=request_params,
            timeout=self.timeout_seconds,
        )
    except requests.ReadTimeout:
        raise TheOddsApiApiError(
            "The Odds API request failed: ReadTimeout",
            error_code="read_timeout",
        ) from None
    except requests.ConnectionError as exc:
        raise TheOddsApiApiError(
            f"The Odds API request failed: {exc.__class__.__name__}",
            error_code="connection_error",
        ) from None
    except requests.RequestException as exc:
        raise TheOddsApiApiError(
            f"The Odds API request failed: {exc.__class__.__name__}",
            error_code="request_error",
        ) from None
    try:
        response.raise_for_status()
    except Exception as exc:
        status_code = getattr(response, "status_code", None)
        retry_after = _retry_after_seconds(getattr(response, "headers", {}) or {})
        provider_message = _response_error_message(response)
        details = [f"The Odds API HTTP error: {exc.__class__.__name__}"]
        if isinstance(status_code, int):
            details.append(f"status={status_code}")
        if provider_message:
            details.append(provider_message)
        raise TheOddsApiApiError(
            "; ".join(details),
            status_code=status_code if isinstance(status_code, int) else None,
            error_code=f"http_{status_code}" if isinstance(status_code, int) else "http_error",
            retry_after_seconds=retry_after,
        ) from None
    payload = response.json()
    self._record_credit_headers(response)
    if isinstance(payload, dict) and payload.get("message"):
        raise TheOddsApiApiError(
            f"The Odds API returned error: {payload['message']}",
            error_code="provider_error",
        )
    return payload
```

Add `_retry_after_seconds(headers)` beside `_int_header`; accept finite non-negative numeric seconds and return `None` otherwise.

- [ ] **Step 6: Replace `get` with capped retry orchestration and redacted logs**

Implement `get` so it performs these exact actions in order:

```python
request_params = dict(params or {})
request_params["apiKey"] = self.api_key
for attempt in range(1, self.max_retries + 2):
    limiter_wait = self.request_limiter.wait(self.recovery_budget)
    started_at = self.clock()
    try:
        payload = self._request_once(endpoint, request_params)
    except TheOddsApiApiError as error:
        elapsed = self.clock() - started_at
        if attempt > 1:
            self.recovery_budget.add_retry_elapsed(elapsed)
        error.attempt_count = attempt
        self.last_request_attempt_count = attempt
        retry_delay = self._retry_delay(error)
        if retry_delay is None or attempt > self.max_retries:
            error.retry_exhausted = retry_delay is not None
            raise
        try:
            self._sleep_for_retry(retry_delay)
        except TheOddsApiExtraTimeBudgetExceededError:
            raise TheOddsApiApiError(
                "The Odds API retry skipped: extra-time budget exhausted",
                error_code="retry_budget_exhausted",
                attempt_count=attempt,
                retry_exhausted=True,
            ) from None
        self.retry_count += 1
        logger.warning(
            "the_odds_api_request_retry trace_id=%s endpoint=%s attempt=%s "
            "error_code=%s limiter_wait=%.3f backoff=%.3f",
            self.trace_id or "-",
            endpoint,
            attempt,
            error.error_code,
            limiter_wait,
            retry_delay,
        )
        continue
    elapsed = self.clock() - started_at
    if attempt > 1:
        self.recovery_budget.add_retry_elapsed(elapsed)
        self.retry_success_count += 1
    self.last_request_attempt_count = attempt
    logger.info(
        "the_odds_api_request_done trace_id=%s endpoint=%s request=%s "
        "attempt=%s elapsed=%.3f",
        self.trace_id or "-",
        endpoint,
        _safe_request_metadata(request_params),
        attempt,
        elapsed,
    )
    return payload
raise RuntimeError("unreachable The Odds API request state")
```

Import `logging`, define `logger = logging.getLogger(__name__)`, and log only the endpoint string plus whitelisted scalar metadata. Never log `request_params`, the full URL, raw response, or the underlying exception text.

Implement the metadata whitelist without `apiKey`:

```python
def _safe_request_metadata(params: dict[str, Any]) -> dict[str, str]:
    allowed = ("regions", "bookmakers", "markets", "dateFormat", "date")
    return {key: str(params[key]) for key in allowed if key in params}
```

- [ ] **Step 7: Run all client tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_client.py -q
```

Expected: all tests pass. Update the existing proxy-error redaction test to construct the client with `max_retries=0`, because that test verifies redaction rather than retry behavior.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/icewine_prediction/sources/the_odds_api_client.py tests/test_the_odds_api_client.py
git commit -m "为The Odds API增加瞬时错误重试"
```

### Task 3: Add Per-Request Cache Outcomes And Partial Match Success

**Files:**
- Modify: `src/icewine_prediction/the_odds_api_sync_runner.py:118-132,277-431,734-849`
- Test: `tests/test_the_odds_api_sync_runner.py`

- [ ] **Step 1: Write failing partial-success and shared-failure-cache tests**

Import `TheOddsApiApiError` and `TheOddsApiExtraTimeBudgetExceededError` in `tests/test_the_odds_api_sync_runner.py` and add:

```python
def test_run_the_odds_api_sync_keeps_other_timepoints_after_one_request_failure(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")

    class OneTimepointFailureClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            params = params or {}
            self.calls.append((endpoint, params))
            self.request_count += 1
            if params.get("date") == "2026-06-26T18:00:00Z":
                raise TheOddsApiApiError(
                    "The Odds API request failed: ReadTimeout",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                )
            return {"data": [_historical_event_payload(params["date"])]}

    client = TheOddsApiSyncClient(OneTimepointFailureClient({}))
    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 26, 18, 51, tzinfo=ZoneInfo("UTC")),
    )

    assert result.processed_match_count == 1
    assert result.match_results[0].match_id == match.id
    assert result.match_results[0].status == "partial_success"
    assert result.match_results[0].attempt_count == 2
    assert result.match_results[0].error_code == "read_timeout"


def test_run_the_odds_api_sync_reuses_failed_historical_request_within_batch(session):
    first = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    second = _add_match(session, home_team_name="Liverpool", away_team_name="Everton")

    class SharedFailureClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            params = params or {}
            self.calls.append((endpoint, params))
            self.request_count += 1
            if params.get("date") == "2026-06-26T18:00:00Z":
                raise TheOddsApiApiError(
                    "The Odds API request failed: ReadTimeout",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                )
            return {
                "data": [
                    _historical_event_payload(params["date"]),
                    _historical_event_payload(
                        params["date"],
                        event_id="historical-event-2",
                        home_team="Liverpool",
                        away_team="Everton",
                    ),
                ]
            }

    raw_client = SharedFailureClient({})
    result = run_the_odds_api_sync_for_session(
        session=session,
        client=TheOddsApiSyncClient(raw_client),
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 26, 18, 51, tzinfo=ZoneInfo("UTC")),
    )

    failed_t60_calls = [
        call for call in raw_client.calls if call[1].get("date") == "2026-06-26T18:00:00Z"
    ]
    assert {item.match_id for item in result.match_results} == {first.id, second.id}
    assert len(failed_t60_calls) == 1


def test_run_the_odds_api_sync_reuses_failed_current_request_within_batch(session):
    first = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    second = _add_match(session, home_team_name="Liverpool", away_team_name="Everton")

    class CurrentFailureClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            params = params or {}
            self.calls.append((endpoint, params))
            self.request_count += 1
            if endpoint.startswith("historical/"):
                return {"data": []}
            raise TheOddsApiApiError(
                "The Odds API request failed: ReadTimeout",
                error_code="read_timeout",
                attempt_count=2,
                retry_exhausted=True,
            )

    raw_client = CurrentFailureClient({})
    result = run_the_odds_api_sync_for_session(
        session=session,
        client=TheOddsApiSyncClient(raw_client),
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 26, 18, 51, tzinfo=ZoneInfo("UTC")),
    )

    current_calls = [call for call in raw_client.calls if not call[0].startswith("historical/")]
    assert len(current_calls) == 1
    assert {item.match_id for item in result.match_results} == {first.id, second.id}
    assert {item.status for item in result.match_results} == {"failed"}
```

- [ ] **Step 2: Run the three runner tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_sync_runner.py::test_run_the_odds_api_sync_keeps_other_timepoints_after_one_request_failure tests\test_the_odds_api_sync_runner.py::test_run_the_odds_api_sync_reuses_failed_historical_request_within_batch tests\test_the_odds_api_sync_runner.py::test_run_the_odds_api_sync_reuses_failed_current_request_within_batch -q
```

Expected: failures because the current timepoint exception escapes and `match_results` does not exist.

- [ ] **Step 3: Add typed request-cache and match-result records**

Add these frozen dataclasses before `TheOddsApiSyncResult`:

```python
@dataclass(frozen=True)
class TheOddsApiCachedRequestResult:
    events: tuple[dict[str, Any], ...] = ()
    error_message: str | None = None
    error_code: str | None = None
    attempt_count: int = 1
    retry_exhausted: bool = False

    @property
    def failed(self) -> bool:
        return self.error_code is not None


@dataclass(frozen=True)
class TheOddsApiMatchSyncResult:
    match_id: int
    status: str
    error_message: str | None = None
    error_code: str | None = None
    attempt_count: int = 1
    retry_exhausted: bool = False
```

Extend `TheOddsApiSyncResult` with backward-compatible defaults:

```python
match_results: tuple[TheOddsApiMatchSyncResult, ...] = ()
not_attempted_match_ids: tuple[int, ...] = ()
trace_id: str | None = None
retry_count: int = 0
retry_success_count: int = 0
rate_limit_wait_seconds: float = 0.0
recovery_elapsed_seconds: float = 0.0
recovery_budget_remaining_seconds: float = 120.0
```

- [ ] **Step 4: Cache both success and failure for historical requests**

Change the historical cache type to:

```python
historical_odds_cache: dict[
    tuple[str, str, str, str, str],
    TheOddsApiCachedRequestResult,
] = {}
events_by_sport_key: dict[str, TheOddsApiCachedRequestResult] = {}
```

Make `_fetch_historical_odds_cached` return `TheOddsApiCachedRequestResult`. On the first call, wrap success as a tuple of events. On `TheOddsApiApiError`, store its sanitized message, `error_code`, `attempt_count`, and `retry_exhausted`. On later calls, return the cached object without requesting again.

Apply the same success/failure wrapper to current-odds requests in `events_by_sport_key`. If one current-odds request exhausts retry, later matches with the same sport key reuse that failure instead of issuing the same endpoint again.

Update `_fetch_historical_snapshots_at_times` to return three values:

```python
return snapshots, raw_source_snapshots, request_failures
```

For every snapshot time, append a failed cache result to `request_failures` and continue the loop. For successful results, map events exactly as today. Set the match-level attempt count to the maximum `attempt_count` among cache results used by that match.

- [ ] **Step 5: Classify matches with usable snapshots plus failures as partial success**

When a match has saved snapshots and at least one request failure, append:

```python
TheOddsApiMatchSyncResult(
    match_id=match.id,
    status="partial_success",
    error_message=request_failures[0].error_message,
    error_code=request_failures[0].error_code,
    attempt_count=max(item.attempt_count for item in request_failures),
    retry_exhausted=any(item.retry_exhausted for item in request_failures),
)
```

When it has snapshots and no failures, append status `success`. Define `attempt_count` as the maximum attempt count of any request used by that match; this makes `2` mean at least one contributing request was retried once.

- [ ] **Step 6: Run runner tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_sync_runner.py -q
```

Expected: all runner tests pass, including existing six-timepoint and shared-success-cache tests.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/icewine_prediction/the_odds_api_sync_runner.py tests/test_the_odds_api_sync_runner.py
git commit -m "记录The Odds API逐场与时点结果"
```

### Task 4: Continue The Batch After A Match Failure

**Files:**
- Modify: `src/icewine_prediction/the_odds_api_sync_runner.py:277-431`
- Test: `tests/test_the_odds_api_sync_runner.py`

- [ ] **Step 1: Write the task-337 multi-match regression test**

Add a dynamic client that produces six empty historical responses, one final timeout for the first sport, and valid events for later sports:

```python
def test_run_the_odds_api_sync_continues_other_matches_after_final_request_failure(
    session,
    caplog,
):
    caplog.set_level("INFO", logger="icewine_prediction.the_odds_api_sync_runner")
    first = _add_match(
        session,
        home_team_name="Valerenga",
        away_team_name="Ham-Kam",
        source_league_id="103",
    )
    second = _add_match(
        session,
        home_team_name="Oddevold",
        away_team_name="Norrby IF",
        source_league_id="114",
    )

    class FirstSportFailureClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            params = params or {}
            self.calls.append((endpoint, params))
            self.request_count += 1
            if "soccer_norway_eliteserien" in endpoint:
                if endpoint.startswith("historical/"):
                    return {"data": []}
                raise TheOddsApiApiError(
                    "The Odds API request failed: ReadTimeout",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                )
            return {
                "data": [
                    _historical_event_payload(
                        params["date"],
                        event_id="sweden-event",
                        home_team="Oddevold",
                        away_team="Norrby IF",
                    )
                ]
            }

    raw_client = FirstSportFailureClient({})
    result = run_the_odds_api_sync_for_session(
        session=session,
        client=TheOddsApiSyncClient(raw_client),
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 26, 18, 51, tzinfo=ZoneInfo("UTC")),
        trace_id="trace-337",
    )

    outcomes = {item.match_id: item for item in result.match_results}
    assert outcomes[first.id].status == "failed"
    assert outcomes[first.id].error_code == "read_timeout"
    assert outcomes[second.id].status == "success"
    assert result.failed_match_count == 1
    assert result.processed_match_count == 1
    assert "trace_id=trace-337" in caplog.text
    assert f"match_id={first.id} status=failed" in caplog.text
    assert f"match_id={second.id} status=success" in caplog.text


def test_run_the_odds_api_sync_marks_remaining_matches_not_attempted_when_pacing_budget_ends(
    session,
):
    first = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    second = _add_match(
        session,
        home_team_name="Liverpool",
        away_team_name="Everton",
        source_league_id="114",
    )

    class ExhaustedBudgetClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            raise TheOddsApiExtraTimeBudgetExceededError(
                "The Odds API extra-time budget exhausted"
            )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=TheOddsApiSyncClient(ExhaustedBudgetClient({})),
        season=2026,
        max_matches=5,
    )

    assert result.not_attempted_match_ids == (first.id, second.id)
    assert {item.status for item in result.match_results} == {"not_attempted"}
```

- [ ] **Step 2: Run the regression test and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_sync_runner.py::test_run_the_odds_api_sync_continues_other_matches_after_final_request_failure tests\test_the_odds_api_sync_runner.py::test_run_the_odds_api_sync_marks_remaining_matches_not_attempted_when_pacing_budget_ends -q
```

Expected: second match is not processed because the current outer exception handler executes `break`.

- [ ] **Step 3: Replace batch break with per-match failure and continue**

In `run_the_odds_api_sync_for_session`, maintain a `match_results` list. Replace the current request exception branch with:

```python
except (TheOddsApiApiError, TheOddsApiRequestBudgetExceededError) as exc:
    error_message = str(exc)
    _store_source_match_status(session, match, None, "failed", error_message)
    match_results.append(
        TheOddsApiMatchSyncResult(
            match_id=match.id,
            status="failed",
            error_message=error_message,
            error_code=getattr(exc, "error_code", "request_budget_exhausted"),
            attempt_count=getattr(exc, "attempt_count", 1),
            retry_exhausted=getattr(exc, "retry_exhausted", False),
        )
    )
    failed += 1
    continue
```

Keep `error_message` on `TheOddsApiSyncResult` only for fatal batch-level failures. Per-match request failures live in `match_results` and must not become a global error.

Catch `TheOddsApiExtraTimeBudgetExceededError` separately. Append the current and remaining selected match IDs to `not_attempted_match_ids`, add a `not_attempted` match result for each, and stop issuing requests because limiter safety cannot be preserved.

- [ ] **Step 4: Add trace-linked runner logs**

Import `logging`, define `logger = logging.getLogger(__name__)`, and add optional `trace_id: str | None = None` to `run_the_odds_api_sync_for_session`.

Log match boundaries and outcomes with fixed metadata rather than payloads:

```python
logger.info(
    "the_odds_api_match_start trace_id=%s match_id=%s sport_key=%s",
    trace_id or "-",
    match.id,
    sport_key,
)
logger.info(
    "the_odds_api_match_result trace_id=%s match_id=%s status=%s error_code=%s",
    trace_id or "-",
    match.id,
    match_result.status,
    match_result.error_code or "-",
)
```

When a cached failure is reused, log:

```python
logger.info(
    "the_odds_api_request_cache_failure trace_id=%s match_id=%s "
    "sport_key=%s error_code=%s",
    trace_id or "-",
    match.id,
    sport_key,
    cached_result.error_code,
)
```

Do not log event payloads, team payloads, raw exceptions, request parameters, or URLs.

- [ ] **Step 5: Populate trace and recovery statistics**

Expose these properties through `TheOddsApiSyncClient` from its raw client, using safe defaults for fakes:

```python
retry_count = getattr(self.client, "retry_count", 0)
retry_success_count = getattr(self.client, "retry_success_count", 0)
recovery_budget = getattr(self.client, "recovery_budget", None)
```

Populate the corresponding `TheOddsApiSyncResult` fields, including `trace_id`. Use `0.0` and `120.0` defaults when an injected fake has no recovery budget.

- [ ] **Step 6: Run runner tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_sync_runner.py -q
```

Expected: all runner tests pass and the task-337 regression processes the second sport after the first fails.

- [ ] **Step 7: Commit Task 4**

```powershell
git add src/icewine_prediction/the_odds_api_sync_runner.py tests/test_the_odds_api_sync_runner.py
git commit -m "隔离The Odds API单场请求失败"
```

### Task 5: Share One Budget Across Seasons And Merge Final Match Statuses

**Files:**
- Modify: `src/icewine_prediction/match_odds_sync_service.py:31-149,211-248`
- Modify: `src/icewine_prediction/the_odds_api_sync_runner.py:535-565`
- Test: `tests/test_match_odds_sync_service.py`

- [ ] **Step 1: Extend the test result helper**

Update `_the_odds_api_result` in `tests/test_match_odds_sync_service.py` to accept exact match outcomes:

```python
def _the_odds_api_result(
    *,
    requests_used: int,
    inserted_snapshot_count: int,
    credits_used: int = 0,
    match_results=(),
    not_attempted_match_ids=(),
    retry_count: int = 0,
    retry_success_count: int = 0,
) -> TheOddsApiSyncResult:
    return TheOddsApiSyncResult(
        processed_match_count=len(
            [item for item in match_results if item.status in {"success", "partial_success"}]
        ),
        matched_count=len(
            [item for item in match_results if item.status in {"success", "partial_success"}]
        ),
        failed_match_count=len([item for item in match_results if item.status == "failed"]),
        inserted_snapshot_count=inserted_snapshot_count,
        skipped_duplicate_snapshot_count=0,
        skipped_existing_odds_count=0,
        asian_handicap_count=inserted_snapshot_count,
        total_goals_count=0,
        match_winner_count=0,
        requests_used=requests_used,
        credits_used=credits_used,
        match_results=tuple(match_results),
        not_attempted_match_ids=tuple(not_attempted_match_ids),
        retry_count=retry_count,
        retry_success_count=retry_success_count,
    )
```

Import `TheOddsApiMatchSyncResult` beside `TheOddsApiSyncResult`.

- [ ] **Step 2: Write failing cross-season and accurate-classification tests**

Add:

```python
def test_run_match_odds_sync_shares_trace_and_recovery_budget_across_seasons(session):
    first = _add_match(session, season=2025)
    second = _add_match(session, season=2026)
    calls = []

    def fake_the_odds_api_sync(**kwargs):
        calls.append(kwargs)
        match_id = next(iter(kwargs["match_ids"]))
        session.add(_snapshot(match_id=match_id, source_name=THE_ODDS_API_SOURCE_NAME, odds=Decimal("1.90")))
        session.commit()
        return _the_odds_api_result(
            requests_used=1,
            inserted_snapshot_count=1,
            match_results=[TheOddsApiMatchSyncResult(match_id=match_id, status="success")],
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[first.id, second.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    assert len(calls) == 2
    assert calls[0]["trace_id"] == calls[1]["trace_id"] == result["trace_id"]
    assert calls[0]["recovery_budget"] is calls[1]["recovery_budget"]


def test_run_match_odds_sync_does_not_copy_one_primary_error_to_other_matches(session, caplog):
    caplog.set_level("INFO", logger="icewine_prediction.match_odds_sync_service")
    failed_match = _add_match(session)
    successful_match = _add_match(session)

    def fake_the_odds_api_sync(**kwargs):
        session.add(
            _snapshot(
                match_id=successful_match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.91"),
            )
        )
        session.commit()
        return _the_odds_api_result(
            requests_used=7,
            inserted_snapshot_count=1,
            match_results=[
                TheOddsApiMatchSyncResult(
                    match_id=failed_match.id,
                    status="failed",
                    error_message="The Odds API request failed: ReadTimeout",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                ),
                TheOddsApiMatchSyncResult(match_id=successful_match.id, status="success"),
            ],
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[failed_match.id, successful_match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        zqcf918_syncer=lambda **kwargs: {
            "success": [],
            "failed": [],
            "skipped": [
                {"match_id": match_id, "message": "missing zqcf918 match ID"}
                for match_id in kwargs["match_ids"]
            ],
            "requests": 0,
            "credits": 0,
        },
    )

    assert _success_match_ids(result) == [successful_match.id]
    assert [item["match_id"] for item in result["failed"]] == [failed_match.id]
    assert result["failed"][0]["error_code"] == "read_timeout"
    assert result["odds_status"] == "partial"
    assert f"trace_id={result['trace_id']}" in caplog.text
    assert f"match_id={failed_match.id} status=failed" in caplog.text


def test_run_match_odds_sync_marks_existing_odds_when_primary_refresh_fails(session):
    match = _add_match(session)
    session.add(_snapshot(match_id=match.id, source_name=ZQCF918_SOURCE_NAME, odds=Decimal("1.90")))
    session.commit()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=lambda **kwargs: _the_odds_api_result(
            requests_used=2,
            inserted_snapshot_count=0,
            match_results=[
                TheOddsApiMatchSyncResult(
                    match_id=match.id,
                    status="failed",
                    error_message="The Odds API request failed: ReadTimeout",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                )
            ],
        ),
    )

    assert result["success"][0]["primary_refresh_status"] == "failed_existing_odds_used"
    assert result["success"][0]["primary_refresh_error"] == "read_timeout"
```

- [ ] **Step 3: Run the new match-sync tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_match_odds_sync_service.py -q
```

Expected: failures for missing trace/budget kwargs, copied batch error behavior, and missing enriched result fields.

- [ ] **Step 4: Create one trace and budget at the unified sync boundary**

At the start of `run_match_odds_sync_for_session`, create:

```python
trace_id = uuid4().hex[:12]
recovery_budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)
```

Import `uuid4` and `TheOddsApiRecoveryBudget`. Pass both values through `_run_provider_sync` and into every The Odds API syncer call. Extend `run_default_the_odds_api_sync_for_session` to pass them into `TheOddsApiClient` and `run_the_odds_api_sync_for_session`; do not recreate either value per season.

For direct CLI runner construction, create a trace/budget only when callers did not supply them.

- [ ] **Step 5: Aggregate per-match primary outcomes instead of one global error**

Maintain:

```python
primary_results: dict[int, TheOddsApiMatchSyncResult] = {}
not_attempted_ids: set[int] = set()
```

Merge every season result into these structures. Keep `result.error_message` only as a fatal batch error and assign it only to IDs in `result.not_attempted_match_ids` that lack a per-match result. Never loop over all season match IDs to copy a normal request error.

Preserve compatibility with injected or older syncers that return an empty `match_results` tuple: derive success from trusted snapshots and derive an affected match's primary error from its `OddsSourceMatch` row. A global `error_message` without per-match evidence is treated as a fatal batch condition and maps only explicitly returned `not_attempted_match_ids`; it must not be copied to every match in the season.

Continue the existing zqcf918 and SBOBET fallback sequence for matches without trusted odds, including primary `not_attempted` matches. Classify the final response with mutually exclusive `success`, `failed`, `skipped`, and `not_attempted` lists.

Populate success items with:

```python
{
    "match_id": match.id,
    "message": "赔率已刷新",
    "source": selected_source,
    "attempt_count": primary.attempt_count if primary else 1,
    "retried": bool(primary and primary.attempt_count > 1),
    "primary_refresh_status": primary_refresh_status,
    "primary_refresh_error": primary.error_code if primary and primary.error_code else None,
}
```

Populate final failures with `error_code`, `failure_stage`, `attempt_count`, `retry_exhausted`, and `fallback_error`. Set `odds_status` to `success`, `partial`, or `failed` from the final mutually exclusive lists.

Aggregate `retry_count`, `retry_success_count`, limiter wait, recovery elapsed, remaining budget, requests, and credits across season results without double-counting the shared budget object.

Calculate `retry_recovered_match_count` after final classification as the number of successful match items with `retried=true` and `primary_refresh_status` in `{"success", "partial_success"}`. Keep `retry_success_count` as the successful HTTP retry count; a shared retry can recover more than one match.

Import `logging`, define `logger = logging.getLogger(__name__)`, and emit one final record per match after primary/fallback classification:

```python
logger.info(
    "match_odds_sync_result trace_id=%s match_id=%s status=%s "
    "primary_refresh_status=%s failure_stage=%s",
    trace_id,
    item["match_id"],
    final_status,
    item.get("primary_refresh_status", "-"),
    item.get("failure_stage", "-"),
)
```

The log uses only normalized status fields. It must not include fallback response payloads or raw exception URLs.

- [ ] **Step 6: Run match-sync and runner tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_match_odds_sync_service.py tests\test_the_odds_api_sync_runner.py -q
```

Expected: all tests pass. Existing fallback-order tests must remain green.

- [ ] **Step 7: Commit Task 5**

```powershell
git add src/icewine_prediction/match_odds_sync_service.py src/icewine_prediction/the_odds_api_sync_runner.py tests/test_match_odds_sync_service.py
git commit -m "精确汇总赔率主源与回退结果"
```

### Task 6: Enrich Automation Summary Without Changing Task Semantics

**Files:**
- Modify: `src/icewine_prediction/paper_automation_service.py:595-628`
- Test: `tests/test_paper_automation_service.py:833-869`

- [ ] **Step 1: Write failing structured-summary tests**

Add this focused test near the existing partial-odds automation test:

```python
def test_execute_task_bark_summarizes_retries_not_attempted_and_old_odds_fallback():
    now = datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING)
    kickoff = datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING)
    sent_messages = []

    with _session() as session:
        match = _seed_match(session, kickoff)
        task = _seed_running_task(
            session,
            match_window_start=kickoff,
            match_window_end=kickoff,
            now=now,
        )
        odds_result = {
            "success": [
                {
                    "match_id": match.id,
                    "primary_refresh_status": "failed_existing_odds_used",
                }
            ],
            "failed": [],
            "skipped": [],
            "not_attempted": [{"match_id": 999}],
            "retry_count": 1,
            "retry_success_count": 1,
            "retry_recovered_match_count": 1,
            "recovery_elapsed_seconds": 46.2,
            "odds_status": "partial",
        }

        result = execute_paper_automation_task(
            session,
            task.id,
            now=now,
            odds_syncer=lambda match_ids: odds_result,
            queue_builder=lambda session_arg, task_arg: _queue_report([]),
            bark_push_url="https://example.com/bark/token",
            bark_sender=lambda push_url, message: sent_messages.append(message)
            or BarkPushResult(success=True),
        )

    body = sent_messages[0].body
    assert "赔率刷新：成功1 失败0 未尝试1" in body
    assert "重试：1次，恢复1场" in body
    assert "旧赔率兜底：1场" in body
    assert "额外耗时：46秒" in body
    assert result.status == "success"
    assert result.result_payload["odds"]["odds_status"] == "partial"
```

Add a backward-compatibility unit test for the old payload shape:

```python
def test_odds_summary_keeps_legacy_shape_readable():
    assert _odds_summary_lines(
        {"success": [1], "failed": [2], "skipped": [3]}
    ) == ["赔率刷新：成功1 失败1 跳过1"]
```

Import `_odds_summary_lines` from the service in the test module.

- [ ] **Step 2: Run the new automation tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_paper_automation_service.py::test_execute_task_bark_summarizes_retries_not_attempted_and_old_odds_fallback tests\test_paper_automation_service.py::test_odds_summary_keeps_legacy_shape_readable -q
```

Expected: collection or assertion failure because `_odds_summary_lines` does not exist and current summary emits one legacy line.

- [ ] **Step 3: Replace the single odds summary string with structured lines**

Change `_execution_summary_lines` to:

```python
return [
    *_odds_summary_lines(odds_sync_result),
    (
        f"候选{queue_report.candidate_count} "
        f"记录{created_count} 跳过{skipped_count}"
    ),
]
```

Implement:

```python
def _odds_summary_lines(odds_sync_result: Any) -> list[str]:
    if not isinstance(odds_sync_result, dict):
        return ["赔率刷新：结果已返回"]
    success_count = _count_result_items(odds_sync_result, "success")
    failed_count = _count_result_items(odds_sync_result, "failed")
    skipped_count = _count_result_items(odds_sync_result, "skipped")
    not_attempted_count = _count_result_items(odds_sync_result, "not_attempted")
    if success_count == failed_count == skipped_count == not_attempted_count == 0:
        return ["赔率刷新：结果已返回"]
    if "not_attempted" not in odds_sync_result:
        return [
            f"赔率刷新：成功{success_count} 失败{failed_count} 跳过{skipped_count}"
        ]
    lines = [
        f"赔率刷新：成功{success_count} 失败{failed_count} 未尝试{not_attempted_count}"
    ]
    retry_count = int(odds_sync_result.get("retry_count", 0) or 0)
    retry_recovered_match_count = int(
        odds_sync_result.get("retry_recovered_match_count", 0) or 0
    )
    if retry_count:
        lines.append(f"重试：{retry_count}次，恢复{retry_recovered_match_count}场")
    old_odds_count = len(
        [
            item
            for item in odds_sync_result.get("success", [])
            if isinstance(item, dict)
            and item.get("primary_refresh_status") == "failed_existing_odds_used"
        ]
    )
    if old_odds_count:
        lines.append(f"旧赔率兜底：{old_odds_count}场")
    recovery_elapsed = float(odds_sync_result.get("recovery_elapsed_seconds", 0.0) or 0.0)
    if recovery_elapsed > 0:
        lines.append(f"额外耗时：{round(recovery_elapsed)}秒")
    return lines
```

Keep `_odds_summary_text` only as a temporary compatibility wrapper if another caller exists; otherwise remove it after confirming with `rg -n "_odds_summary_text" src tests` that there are no consumers.

- [ ] **Step 4: Run automation tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_paper_automation_service.py -q
```

Expected: all automation service tests pass, including the existing partial-failure task-status assertion.

- [ ] **Step 5: Commit Task 6**

```powershell
git add src/icewine_prediction/paper_automation_service.py tests/test_paper_automation_service.py
git commit -m "完善自动任务赔率恢复摘要"
```

### Task 7: Run Focused And Cross-Layer Verification

**Files:**
- Verify only; modify code only if a failing test identifies a requirement regression.

- [ ] **Step 1: Run all touched-area tests**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_the_odds_api_client.py tests\test_the_odds_api_sync_runner.py tests\test_match_odds_sync_service.py tests\test_paper_automation_service.py -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run Web API regressions for odds and automation endpoints**

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_web_console_api.py -q
```

Expected: all Web console API tests pass. No response-schema consumer fails because old keys remain present.

- [ ] **Step 3: Verify formatting and staged scope**

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` prints nothing. `git status --short` shows only files from this plan plus any pre-existing user change that has deliberately remained unstaged.

- [ ] **Step 4: Inspect the final diff against the design**

Verify each statement with code and test evidence:

```text
1. Process-wide request start interval is 1.0 second.
2. ReadTimeout, connection errors, 429, and selected 5xx retry at most once.
3. Added waits and retry execution consume no more than 120 seconds.
4. One match failure does not break later matches.
5. Shared request failures are cached within one sync.
6. Primary errors are attached only to affected matches.
7. Existing odds and fallback success remain distinguishable from refresh success.
8. API keys and complete request URLs are absent from logs.
9. PaperAutomationTask status semantics remain unchanged.
```

- [ ] **Step 5: Commit any final test-only adjustment if needed**

If Step 1 or Step 2 required a test fixture update that does not change behavior, commit only those verified files:

```powershell
git add tests/test_web_console_api.py
git commit -m "补充赔率韧性跨层回归验证"
```

If no adjustment was needed, do not create an empty commit.

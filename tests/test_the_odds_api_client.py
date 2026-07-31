import logging
import time
from threading import Event, Thread

import pytest
import requests

from icewine_prediction.sources.the_odds_api_client import (
    MissingTheOddsApiKeyError,
    TheOddsApiApiError,
    TheOddsApiClient,
    TheOddsApiExtraTimeBudgetExceededError,
    TheOddsApiRecoveryBudget,
    TheOddsApiRequestBudgetExceededError,
    TheOddsApiRequestLimiter,
    _retry_after_seconds,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeTime:
    def __init__(self, now=100.0, oversleep_seconds=0.0):
        self.now = now
        self.oversleep_seconds = oversleep_seconds
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds + self.oversleep_seconds


class AdvancingFakeTime(FakeTime):
    def monotonic(self):
        current = self.now
        self.now += 0.1
        return current


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit_seconds": -1.0},
        {"limit_seconds": float("nan")},
        {"limit_seconds": float("inf")},
        {"limiter_wait_seconds": -1.0},
        {"backoff_wait_seconds": float("nan")},
        {"retry_elapsed_seconds": float("inf")},
    ],
)
def test_the_odds_api_recovery_budget_rejects_invalid_initial_values(kwargs):
    with pytest.raises(ValueError):
        TheOddsApiRecoveryBudget(**kwargs)


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

    assert limiter.wait(budget) == 0.0
    with pytest.raises(TheOddsApiExtraTimeBudgetExceededError):
        limiter.wait(budget)

    assert fake_time.sleeps == []


def test_the_odds_api_request_limiter_does_not_wait_on_first_call_at_clock_zero():
    fake_time = FakeTime(now=0.0)
    budget = TheOddsApiRecoveryBudget()
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert limiter.wait(budget) == 0.0
    assert fake_time.sleeps == []
    assert budget.limiter_wait_seconds == 0.0


def test_the_odds_api_request_limiter_does_not_charge_immediate_lock_acquisition():
    fake_time = AdvancingFakeTime(now=0.0)
    budget = TheOddsApiRecoveryBudget(limit_seconds=0.0)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=0.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert limiter.wait(budget) == 0.0
    assert fake_time.sleeps == []
    assert budget.limiter_wait_seconds == 0.0


def test_the_odds_api_request_limiter_charges_actual_oversleep():
    fake_time = FakeTime(oversleep_seconds=0.5)
    budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert limiter.wait(budget) == 0.0
    fake_time.now += 0.25

    assert limiter.wait(budget) == pytest.approx(1.25)
    assert fake_time.sleeps == [pytest.approx(0.75)]
    assert budget.limiter_wait_seconds == pytest.approx(1.25)


def test_the_odds_api_request_limiter_refuses_permit_after_oversleep_exhausts_budget():
    fake_time = FakeTime(oversleep_seconds=0.5)
    budget = TheOddsApiRecoveryBudget(limit_seconds=1.0)
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert limiter.wait(budget) == 0.0
    fake_time.now += 0.25

    with pytest.raises(TheOddsApiExtraTimeBudgetExceededError):
        limiter.wait(budget)

    assert budget.limiter_wait_seconds == pytest.approx(1.25)
    assert budget.consumed_seconds == pytest.approx(1.25)
    assert budget.remaining_seconds == 0.0


def test_the_odds_api_request_limiter_bounds_lock_wait_by_remaining_budget():
    budget = TheOddsApiRecoveryBudget(limit_seconds=0.05)
    limiter = TheOddsApiRequestLimiter(cooldown_seconds=0.0)
    errors = []
    limiter._lock.acquire()

    thread = Thread(target=lambda: _capture_limiter_error(limiter, budget, errors))
    thread.start()
    thread.join(timeout=1.0)
    completed_within_budget = not thread.is_alive()
    limiter._lock.release()
    thread.join(timeout=1.0)

    assert completed_within_budget
    assert len(errors) == 1
    assert isinstance(errors[0], TheOddsApiExtraTimeBudgetExceededError)
    assert budget.remaining_seconds == 0.0


def _capture_limiter_error(limiter, budget, errors):
    try:
        limiter.wait(budget)
    except Exception as exc:
        errors.append(exc)


def _no_wait_limiter():
    return TheOddsApiRequestLimiter(cooldown_seconds=0.0)


def _controlled_client(responses, timeout_seconds=40, recovery_limit=120):
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


def test_the_odds_api_client_adds_api_key_and_counts_requests():
    session = FakeSession([FakeResponse({"ok": True})])
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=12,
        request_budget=2,
        session=session,
        request_limiter=_no_wait_limiter(),
    )

    payload = client.get("sports/soccer_epl/odds", {"regions": "eu"})

    assert payload == {"ok": True}
    assert client.request_count == 1
    assert session.calls[0][0] == "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
    assert session.calls[0][1]["apiKey"] == "secret"
    assert session.calls[0][1]["regions"] == "eu"
    assert session.calls[0][2] == 12


def test_the_odds_api_client_tracks_credit_headers_alongside_request_count():
    session = FakeSession(
        [
            FakeResponse(
                {"ok": True},
                headers={
                    "x-requests-last": "30",
                    "x-requests-used": "130",
                    "x-requests-remaining": "870",
                },
            ),
            FakeResponse(
                {"ok": True},
                headers={
                    "x-requests-last": "5",
                    "x-requests-used": "135",
                    "x-requests-remaining": "865",
                },
            ),
        ]
    )
    client = TheOddsApiClient(
        api_key="secret",
        request_budget=2,
        session=session,
        request_limiter=_no_wait_limiter(),
    )

    client.get("historical/sports/soccer_epl/odds")
    client.get("sports/soccer_epl/odds")

    assert client.request_count == 2
    assert client.credit_count == 35
    assert client.last_credit_count == 5
    assert client.provider_requests_used == 135
    assert client.provider_requests_remaining == 865


def test_the_odds_api_client_default_session_ignores_environment_proxy():
    client = TheOddsApiClient(
        api_key="secret",
        request_limiter=_no_wait_limiter(),
    )

    assert client.session.trust_env is False


def test_the_odds_api_client_requires_api_key():
    with pytest.raises(MissingTheOddsApiKeyError):
        TheOddsApiClient(api_key=None)


def test_the_odds_api_api_error_preserves_retry_context():
    error = TheOddsApiApiError(
        "request failed",
        status_code=429,
        error_code="http_429",
        retry_after_seconds=12.0,
        attempt_count=2,
        retry_exhausted=True,
    )

    assert str(error) == "request failed"
    assert error.status_code == 429
    assert error.error_code == "http_429"
    assert error.retry_after_seconds == 12.0
    assert error.attempt_count == 2
    assert error.retry_exhausted is True


def test_the_odds_api_client_enforces_request_budget():
    client = TheOddsApiClient(
        api_key="secret",
        request_budget=0,
        session=FakeSession([]),
        request_limiter=_no_wait_limiter(),
    )

    with pytest.raises(TheOddsApiRequestBudgetExceededError):
        client.get("sports")


def test_the_odds_api_client_wraps_json_error_payload():
    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({"message": "Invalid API key"})]),
        request_limiter=_no_wait_limiter(),
        max_retries=0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert "Invalid API key" in str(exc_info.value)


def test_the_odds_api_client_api_error_does_not_expose_api_key_in_url():
    class UrlLeakingResponse(FakeResponse):
        def raise_for_status(self):
            raise RuntimeError(
                "429 Client Error for url: "
                "https://api.the-odds-api.com/v4/sports?apiKey=secret"
            )

    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([UrlLeakingResponse({})]),
        request_limiter=_no_wait_limiter(),
        max_retries=0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)


def test_the_odds_api_client_http_error_includes_response_message_without_api_key():
    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({"message": "Markets not available"}, status_code=422)]),
        request_limiter=_no_wait_limiter(),
        max_retries=0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports/soccer_epl/odds", {"apiKey": "secret"})

    assert "status=422" in str(exc_info.value)
    assert "Markets not available" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)


def test_the_odds_api_client_wraps_request_errors_without_exposing_api_key():
    class RequestFailingSession:
        def get(self, url, params, timeout):
            raise requests.exceptions.ProxyError(
                "Proxy failed for url: "
                "https://api.the-odds-api.com/v4/sports?apiKey=secret"
            )

    client = TheOddsApiClient(
        api_key="secret",
        session=RequestFailingSession(),
        request_limiter=_no_wait_limiter(),
        max_retries=0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert client.request_count == 1
    assert "ProxyError" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)


def test_the_odds_api_client_retries_read_timeout_and_tracks_recovery():
    client, fake_time, budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe secret"), FakeResponse({"ok": True})]
    )

    payload = client.get("sports", {"regions": "eu"})

    assert payload == {"ok": True}
    assert client.request_count == 2
    assert client.retry_count == 1
    assert client.retry_success_count == 1
    assert client.last_request_attempt_count == 2
    assert budget.backoff_wait_seconds == pytest.approx(5.0)
    assert fake_time.sleeps == [pytest.approx(5.0)]


def test_the_odds_api_client_clamps_retries_to_one_attempt():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget()
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=40,
        request_budget=20,
        session=FakeSession(
            [
                requests.exceptions.ReadTimeout("first"),
                requests.exceptions.ReadTimeout("second"),
                requests.exceptions.ReadTimeout("third"),
            ]
        ),
        request_limiter=TheOddsApiRequestLimiter(
            cooldown_seconds=1.0,
            clock=fake_time.monotonic,
            sleeper=fake_time.sleep,
        ),
        recovery_budget=budget,
        max_retries=2,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.attempt_count == 2
    assert exc_info.value.retry_exhausted is True
    assert client.request_count == 2
    assert client.retry_count == 1
    assert len(client.session.responses) == 1


def test_the_odds_api_client_uses_retry_after_for_rate_limit():
    client, fake_time, budget = _controlled_client(
        [
            FakeResponse({}, status_code=429, headers={"Retry-After": "12"}),
            FakeResponse({"ok": True}),
        ]
    )

    assert client.get("sports") == {"ok": True}
    assert budget.backoff_wait_seconds == pytest.approx(12.0)
    assert fake_time.sleeps == [pytest.approx(12.0)]


def test_the_odds_api_retry_after_accepts_numeric_zero():
    assert _retry_after_seconds({"Retry-After": 0}) == 0.0


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_the_odds_api_client_retries_transient_server_errors(status_code):
    client, fake_time, budget = _controlled_client(
        [FakeResponse({}, status_code=status_code), FakeResponse({"ok": True})]
    )

    assert client.get("sports") == {"ok": True}
    assert client.request_count == 2
    assert budget.backoff_wait_seconds == pytest.approx(5.0)
    assert fake_time.sleeps == [pytest.approx(5.0)]


def test_the_odds_api_client_retries_connection_error():
    client, fake_time, budget = _controlled_client(
        [requests.exceptions.ConnectionError("unsafe secret"), FakeResponse({"ok": True})]
    )

    assert client.get("sports") == {"ok": True}
    assert client.request_count == 2
    assert budget.backoff_wait_seconds == pytest.approx(5.0)
    assert fake_time.sleeps == [pytest.approx(5.0)]


@pytest.mark.parametrize("retry_after", [None, "invalid", "-1"])
def test_the_odds_api_client_uses_default_rate_limit_backoff(retry_after):
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    client, fake_time, budget = _controlled_client(
        [FakeResponse({}, status_code=429, headers=headers), FakeResponse({"ok": True})]
    )

    assert client.get("sports") == {"ok": True}
    assert budget.backoff_wait_seconds == pytest.approx(15.0)
    assert fake_time.sleeps == [pytest.approx(15.0)]


@pytest.mark.parametrize("status_code", [401, 403, 422])
def test_the_odds_api_client_does_not_retry_permanent_http_errors(status_code):
    client, fake_time, _budget = _controlled_client(
        [FakeResponse({"message": "request rejected"}, status_code=status_code)]
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.error_code == f"http_{status_code}"
    assert exc_info.value.attempt_count == 1
    assert exc_info.value.retry_exhausted is False
    assert client.request_count == 1
    assert fake_time.sleeps == []


def test_the_odds_api_client_refuses_retry_when_recovery_budget_cannot_cover_attempt():
    client, fake_time, _budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe secret")],
        timeout_seconds=40,
        recovery_limit=44,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.error_code == "retry_budget_exhausted"
    assert exc_info.value.attempt_count == 1
    assert exc_info.value.retry_exhausted is True
    assert client.request_count == 1
    assert fake_time.sleeps == []


def test_the_odds_api_client_propagates_extra_time_budget_error_before_first_attempt():
    fake_time = FakeTime()
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )
    limiter.wait(TheOddsApiRecoveryBudget())
    session = FakeSession([FakeResponse({"ok": True})])
    client = TheOddsApiClient(
        api_key="secret",
        request_budget=20,
        session=session,
        request_limiter=limiter,
        recovery_budget=TheOddsApiRecoveryBudget(limit_seconds=0.5),
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(TheOddsApiExtraTimeBudgetExceededError):
        client.get("sports")

    assert client.request_count == 0
    assert session.calls == []
    assert fake_time.sleeps == []


def test_the_odds_api_client_preflights_combined_limiter_and_backoff_wait():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget(limit_seconds=49)
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=40,
        request_budget=20,
        session=FakeSession(
            [requests.exceptions.ReadTimeout("unsafe"), FakeResponse({"ok": True})]
        ),
        request_limiter=TheOddsApiRequestLimiter(
            cooldown_seconds=10.0,
            clock=fake_time.monotonic,
            sleeper=fake_time.sleep,
        ),
        recovery_budget=budget,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.error_code == "retry_budget_exhausted"
    assert exc_info.value.attempt_count == 1
    assert client.request_count == 1
    assert client.retry_count == 0
    assert fake_time.sleeps == []


def test_the_odds_api_client_sleeps_once_for_later_limiter_deadline():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget(limit_seconds=120)
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=40,
        request_budget=20,
        session=FakeSession(
            [requests.exceptions.ReadTimeout("unsafe"), FakeResponse({"ok": True})]
        ),
        request_limiter=TheOddsApiRequestLimiter(
            cooldown_seconds=10.0,
            clock=fake_time.monotonic,
            sleeper=fake_time.sleep,
        ),
        recovery_budget=budget,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert client.get("sports") == {"ok": True}
    assert client.request_count == 2
    assert client.retry_count == 1
    assert fake_time.sleeps == [pytest.approx(10.0)]
    assert budget.backoff_wait_seconds == pytest.approx(5.0)
    assert budget.limiter_wait_seconds == pytest.approx(5.0)
    assert budget.consumed_seconds == pytest.approx(10.0)


def test_the_odds_api_client_checks_request_budget_before_retry_wait():
    client, fake_time, _budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe"), FakeResponse({"ok": True})]
    )
    client.request_budget = 1

    with pytest.raises(TheOddsApiRequestBudgetExceededError):
        client.get("sports")

    assert client.request_count == 1
    assert client.retry_count == 0
    assert client.last_request_attempt_count == 1
    assert fake_time.sleeps == []


def test_the_odds_api_client_checks_request_budget_before_ordinary_limiter_wait():
    fake_time = FakeTime()
    budget = TheOddsApiRecoveryBudget()
    client = TheOddsApiClient(
        api_key="secret",
        request_budget=1,
        session=FakeSession([FakeResponse({"ok": True})]),
        request_limiter=TheOddsApiRequestLimiter(
            cooldown_seconds=1.0,
            clock=fake_time.monotonic,
            sleeper=fake_time.sleep,
        ),
        recovery_budget=budget,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    assert client.get("sports") == {"ok": True}
    fake_time.now += 0.25

    with pytest.raises(TheOddsApiRequestBudgetExceededError):
        client.get("sports")

    assert client.request_count == 1
    assert fake_time.sleeps == []
    assert budget.consumed_seconds == 0.0


def test_the_odds_api_client_charges_actual_backoff_oversleep_before_exhausting_budget():
    client, fake_time, budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe secret")],
        timeout_seconds=40,
        recovery_limit=45,
    )
    fake_time.oversleep_seconds = 0.5

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.error_code == "retry_budget_exhausted"
    assert budget.backoff_wait_seconds == pytest.approx(5.5)
    assert budget.remaining_seconds == pytest.approx(39.5)
    assert fake_time.sleeps == [pytest.approx(5.0)]


def test_the_odds_api_client_charges_actual_retry_execution_time():
    client, fake_time, budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe secret"), FakeResponse({"ok": True})]
    )
    successful_response = client.session.responses[1]
    original_json = successful_response.json

    def advancing_json():
        fake_time.now += 2.0
        return original_json()

    successful_response.json = advancing_json

    assert client.get("sports") == {"ok": True}
    assert budget.retry_elapsed_seconds == pytest.approx(2.0)


def test_the_odds_api_client_retry_log_is_traceable_and_redacted(caplog):
    client, _fake_time, _budget = _controlled_client(
        [requests.exceptions.ReadTimeout("apiKey=secret"), FakeResponse({"ok": True})]
    )

    with caplog.at_level("WARNING"):
        client.get("sports", {"regions": "eu", "apiKey": "secret"})

    retry_record = next(record for record in caplog.records if record.levelname == "WARNING")
    assert retry_record.trace_id == "trace-test"
    assert retry_record.endpoint == "sports"
    assert retry_record.attempt == 1
    assert retry_record.error_code == "read_timeout"
    assert retry_record.limiter_wait == 0.0
    assert retry_record.backoff == pytest.approx(5.0)
    assert "trace-test" in caplog.text
    assert "secret" not in caplog.text
    assert "apiKey" not in caplog.text


def test_the_odds_api_client_success_log_contains_only_safe_request_metadata(caplog):
    client, _fake_time, _budget = _controlled_client([FakeResponse({"ok": True})])

    with caplog.at_level("INFO"):
        client.get(
            "sports",
            {
                "regions": "eu",
                "markets": "h2h",
                "apiKey": "secret",
                "unsafe": "do-not-log",
            },
        )

    success_record = next(record for record in caplog.records if record.levelname == "INFO")
    assert success_record.trace_id == "trace-test"
    assert success_record.endpoint == "sports"
    assert success_record.regions == "eu"
    assert success_record.markets == "h2h"
    assert not hasattr(success_record, "apiKey")
    assert not hasattr(success_record, "unsafe")
    assert "secret" not in caplog.text
    assert "apiKey" not in caplog.text
    assert "do-not-log" not in caplog.text


def test_the_odds_api_client_sanitizes_safe_metadata_values(caplog):
    api_key = "K9Q8W7E6R5"
    client = TheOddsApiClient(
        api_key=api_key,
        session=FakeSession([FakeResponse({"ok": True})]),
        request_limiter=_no_wait_limiter(),
        trace_id="metadata-test",
    )

    with caplog.at_level("INFO"):
        client.get(
            "sports",
            {
                "regions": f"eu\napiKey={api_key}",
                "bookmakers": f"https://book.test/path?token={api_key}",
                "markets": "h2h\r\nforged=yes",
                "dateFormat": "iso",
                "date": "2" * 300,
            },
        )

    record = next(record for record in caplog.records if record.levelname == "INFO")
    assert record.regions == "<redacted>"
    assert record.bookmakers == "<redacted>"
    assert record.markets == "h2h forged=yes"
    assert record.dateFormat == "iso"
    assert len(record.date) <= 160
    assert api_key not in caplog.text
    assert "apiKey" not in caplog.text
    assert "\nforged" not in record.getMessage()


def test_the_odds_api_client_rejects_scalar_subclasses_with_unsafe_repr(caplog):
    class EvilInt(int):
        def __repr__(self):
            return "1 apiKey=secret\nforged-int=yes"

    class EvilFloat(float):
        def __repr__(self):
            return "1.5 apiKey=secret\nforged-float=yes"

    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({"ok": True})]),
        request_limiter=_no_wait_limiter(),
        trace_id="metadata-subclass-test",
    )

    with caplog.at_level("INFO"):
        client.get(
            "sports",
            {
                "regions": EvilInt(1),
                "bookmakers": EvilFloat(1.5),
                "markets": "h2h",
            },
        )

    record = next(record for record in caplog.records if record.levelname == "INFO")
    assert not hasattr(record, "regions")
    assert not hasattr(record, "bookmakers")
    assert record.markets == "h2h"
    assert "apiKey" not in caplog.text
    assert "secret" not in caplog.text
    assert "forged-int" not in caplog.text
    assert "forged-float" not in caplog.text


@pytest.mark.parametrize("status_code", [200, 422])
def test_the_odds_api_client_redacts_sensitive_provider_messages(status_code):
    api_key = "credential-12345"
    payload = {
        "message": (
            "provider failure for https://api.the-odds-api.com/v4/sports"
            f"?apiKey={api_key}"
        )
    }
    client = TheOddsApiClient(
        api_key=api_key,
        session=FakeSession([FakeResponse(payload, status_code=status_code)]),
        request_limiter=_no_wait_limiter(),
        max_retries=0,
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    error_text = str(exc_info.value)
    assert api_key not in error_text
    assert "apiKey" not in error_text
    assert "https://" not in error_text


def test_the_odds_api_client_logs_endpoint_path_without_query_or_fragment(caplog):
    client, _fake_time, _budget = _controlled_client(
        [requests.exceptions.ReadTimeout("unsafe"), FakeResponse({"ok": True})]
    )

    with caplog.at_level("INFO"):
        client.get("sports?apiKey=secret#fragment", {"regions": "eu"})

    assert {record.endpoint for record in caplog.records} == {"sports"}
    assert "apiKey" not in caplog.text
    assert "secret" not in caplog.text
    assert "?" not in caplog.text
    assert "#fragment" not in caplog.text


def test_the_odds_api_client_wraps_invalid_json_without_raw_error_text():
    class BadJsonResponse(FakeResponse):
        def json(self):
            raise ValueError("raw decoder detail apiKey=secret")

    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([BadJsonResponse(None)]),
        request_limiter=_no_wait_limiter(),
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert exc_info.value.error_code == "response_decode_error"
    assert exc_info.value.attempt_count == 1
    assert exc_info.value.retry_exhausted is False
    assert "raw decoder detail" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)
    assert client.request_count == 1
    assert client.retry_count == 0


def test_the_odds_api_client_revalidates_retry_permit_after_logging_delay():
    cooldown_seconds = 0.05
    retry_log_reached = Event()
    release_retry_log = Event()
    request_times = {}
    errors = []

    class RetryingSession:
        def __init__(self):
            self.call_count = 0

        def get(self, url, params, timeout):
            self.call_count += 1
            if self.call_count == 1:
                raise requests.exceptions.ReadTimeout("retry")
            request_times["retry"] = time.monotonic()
            return FakeResponse({"ok": True})

    class RecordingSession:
        def get(self, url, params, timeout):
            request_times["other"] = time.monotonic()
            return FakeResponse({"ok": True})

    class BlockingRetryHandler(logging.Handler):
        def emit(self, record):
            if getattr(record, "trace_id", None) == "stale-retry-test":
                retry_log_reached.set()
                release_retry_log.wait(timeout=2.0)

    limiter = TheOddsApiRequestLimiter(cooldown_seconds=cooldown_seconds)
    retrying_client = TheOddsApiClient(
        api_key="secret",
        session=RetryingSession(),
        request_limiter=limiter,
        trace_id="stale-retry-test",
    )
    retrying_client._retry_delay = lambda _error: 0.0
    other_client = TheOddsApiClient(
        api_key="secret",
        session=RecordingSession(),
        request_limiter=limiter,
        trace_id="other-test",
    )
    module_logger = logging.getLogger(
        "icewine_prediction.sources.the_odds_api_client"
    )
    handler = BlockingRetryHandler()
    previous_level = module_logger.level
    module_logger.setLevel(logging.WARNING)
    module_logger.addHandler(handler)

    def run_retry():
        try:
            retrying_client.get("sports")
        except Exception as exc:
            errors.append(exc)

    thread = Thread(target=run_retry)
    try:
        thread.start()
        assert retry_log_reached.wait(timeout=2.0)
        other_client.get("sports")
        release_retry_log.set()
        thread.join(timeout=2.0)
    finally:
        release_retry_log.set()
        thread.join(timeout=2.0)
        module_logger.removeHandler(handler)
        module_logger.setLevel(previous_level)

    assert not thread.is_alive()
    assert errors == []
    assert request_times["retry"] - request_times["other"] >= 0.045


def test_the_odds_api_clients_share_request_limiter_timing():
    fake_time = FakeTime()
    limiter = TheOddsApiRequestLimiter(
        cooldown_seconds=1.0,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )
    first_client = TheOddsApiClient(
        api_key="first-secret",
        session=FakeSession([FakeResponse({"ok": True})]),
        request_limiter=limiter,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )
    second_client = TheOddsApiClient(
        api_key="second-secret",
        session=FakeSession([FakeResponse({"ok": True})]),
        request_limiter=limiter,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    first_client.get("sports")
    fake_time.now += 0.25
    second_client.get("sports")

    assert fake_time.sleeps == [pytest.approx(0.75)]

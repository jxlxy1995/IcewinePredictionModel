from threading import Thread

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
        return self.responses.pop(0)


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


def test_the_odds_api_client_adds_api_key_and_counts_requests():
    session = FakeSession([FakeResponse({"ok": True})])
    client = TheOddsApiClient(
        api_key="secret",
        timeout_seconds=12,
        request_budget=2,
        session=session,
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
    )

    client.get("historical/sports/soccer_epl/odds")
    client.get("sports/soccer_epl/odds")

    assert client.request_count == 2
    assert client.credit_count == 35
    assert client.last_credit_count == 5
    assert client.provider_requests_used == 135
    assert client.provider_requests_remaining == 865


def test_the_odds_api_client_default_session_ignores_environment_proxy():
    client = TheOddsApiClient(api_key="secret")

    assert client.session.trust_env is False


def test_the_odds_api_client_requires_api_key():
    with pytest.raises(MissingTheOddsApiKeyError):
        TheOddsApiClient(api_key=None)


def test_the_odds_api_client_enforces_request_budget():
    client = TheOddsApiClient(
        api_key="secret",
        request_budget=0,
        session=FakeSession([]),
    )

    with pytest.raises(TheOddsApiRequestBudgetExceededError):
        client.get("sports")


def test_the_odds_api_client_wraps_json_error_payload():
    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({"message": "Invalid API key"})]),
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
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)


def test_the_odds_api_client_http_error_includes_response_message_without_api_key():
    client = TheOddsApiClient(
        api_key="secret",
        session=FakeSession([FakeResponse({"message": "Markets not available"}, status_code=422)]),
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
    )

    with pytest.raises(TheOddsApiApiError) as exc_info:
        client.get("sports")

    assert client.request_count == 1
    assert "ProxyError" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)

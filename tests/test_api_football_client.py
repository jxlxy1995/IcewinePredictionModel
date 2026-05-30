import pytest
from requests import ConnectionError

from icewine_prediction.sources.api_football_client import (
    ApiFootballApiError,
    ApiFootballClient,
    MissingApiKeyError,
    RequestBudgetExceededError,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError

            raise HTTPError(f"{self.status_code} Client Error")
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append((url, headers, params, timeout))
        return FakeResponse({"errors": {}, "results": 1, "response": [{"ok": True}]})


class ErrorSession:
    def get(self, url, headers, params, timeout):
        return FakeResponse({"errors": {"season": "The Season field is required."}, "results": 0})


class HttpErrorSession:
    def get(self, url, headers, params, timeout):
        return FakeResponse({"message": "Too Many Requests"}, status_code=429)


class FlakyConnectionSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, params, timeout):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("connection reset by peer")
        return FakeResponse({"errors": {}, "results": 1, "response": [{"ok": True}]})


class AlwaysConnectionErrorSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, headers, params, timeout):
        self.calls += 1
        raise ConnectionError("connection reset by peer")


def test_client_requires_api_key():
    with pytest.raises(MissingApiKeyError):
        ApiFootballClient(base_url="https://example.test", api_key=None)


def test_client_sends_api_key_header_and_counts_requests():
    session = FakeSession()
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        timeout_seconds=7,
        daily_request_budget=2,
        session=session,
    )

    payload = client.get("fixtures", {"league": 39})

    assert payload["results"] == 1
    assert client.request_count == 1
    assert session.calls[0][0] == "https://example.test/fixtures"
    assert session.calls[0][1]["x-apisports-key"] == "secret"
    assert session.calls[0][2] == {"league": 39}
    assert session.calls[0][3] == 7


def test_client_blocks_when_budget_is_exceeded():
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        daily_request_budget=0,
        session=FakeSession(),
    )

    with pytest.raises(RequestBudgetExceededError):
        client.get("fixtures", {})


def test_client_raises_api_error_when_response_contains_errors():
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        session=ErrorSession(),
    )

    with pytest.raises(ApiFootballApiError, match="season"):
        client.get("fixtures", {})


def test_client_wraps_http_errors_and_counts_request():
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        session=HttpErrorSession(),
    )

    with pytest.raises(ApiFootballApiError, match="429"):
        client.get("odds", {"fixture": "1001"})

    assert client.request_count == 1


def test_client_retries_transient_request_errors_once():
    session = FlakyConnectionSession()
    sleeps: list[float] = []
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        session=session,
        max_retries=1,
        retry_cooldown_seconds=2.0,
        sleep=sleeps.append,
    )

    payload = client.get("fixtures", {"id": "1523174"})

    assert payload["results"] == 1
    assert session.calls == 2
    assert client.request_count == 2
    assert sleeps == [2.0]


def test_client_applies_request_cooldown_between_requests():
    session = FakeSession()
    sleeps: list[float] = []
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        session=session,
        request_cooldown_seconds=0.8,
        sleep=sleeps.append,
    )

    client.get("fixtures", {"id": "1001"})
    client.get("fixtures", {"id": "1002"})

    assert client.request_count == 2
    assert sleeps == [0.8]


def test_client_wraps_request_errors_after_retry_budget_is_exhausted():
    session = AlwaysConnectionErrorSession()
    client = ApiFootballClient(
        base_url="https://example.test",
        api_key="secret",
        session=session,
        max_retries=1,
        retry_cooldown_seconds=0.0,
        sleep=lambda seconds: None,
    )

    with pytest.raises(ApiFootballApiError, match="connection reset by peer"):
        client.get("fixtures", {"id": "1523174"})

    assert session.calls == 2
    assert client.request_count == 2

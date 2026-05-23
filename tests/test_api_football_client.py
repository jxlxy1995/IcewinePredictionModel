import pytest

from icewine_prediction.sources.api_football_client import (
    ApiFootballClient,
    MissingApiKeyError,
    RequestBudgetExceededError,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append((url, headers, params, timeout))
        return FakeResponse({"errors": {}, "results": 1, "response": [{"ok": True}]})


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

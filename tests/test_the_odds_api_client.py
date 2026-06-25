import pytest
import requests

from icewine_prediction.sources.the_odds_api_client import (
    MissingTheOddsApiKeyError,
    TheOddsApiApiError,
    TheOddsApiClient,
    TheOddsApiRequestBudgetExceededError,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

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

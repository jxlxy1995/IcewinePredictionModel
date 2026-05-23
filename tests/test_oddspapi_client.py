import pytest

from icewine_prediction.sources.oddspapi_client import (
    MissingOddsPapiKeyError,
    OddsPapiApiError,
    OddsPapiClient,
    OddsPapiRequestBudgetExceededError,
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


def test_oddspapi_client_adds_api_key_and_counts_requests():
    session = FakeSession([FakeResponse({"ok": True})])
    client = OddsPapiClient(
        base_url="https://api.oddspapi.io/v4",
        api_key="secret",
        timeout_seconds=12,
        request_budget=2,
        session=session,
    )

    payload = client.get("fixtures", {"sportId": 10})

    assert payload == {"ok": True}
    assert client.request_count == 1
    assert session.calls[0][0] == "https://api.oddspapi.io/v4/fixtures"
    assert session.calls[0][1]["apiKey"] == "secret"
    assert session.calls[0][1]["sportId"] == 10


def test_oddspapi_client_requires_api_key():
    with pytest.raises(MissingOddsPapiKeyError):
        OddsPapiClient(base_url="https://api.oddspapi.io/v4", api_key=None)


def test_oddspapi_client_enforces_request_budget():
    client = OddsPapiClient(
        base_url="https://api.oddspapi.io/v4",
        api_key="secret",
        request_budget=0,
        session=FakeSession([]),
    )

    with pytest.raises(OddsPapiRequestBudgetExceededError):
        client.get("fixtures")


def test_oddspapi_client_raises_api_error_for_json_error_payload():
    client = OddsPapiClient(
        base_url="https://api.oddspapi.io/v4",
        api_key="secret",
        session=FakeSession([FakeResponse({"error": {"message": "rate limited"}})]),
    )

    with pytest.raises(OddsPapiApiError):
        client.get("fixtures")


def test_oddspapi_client_api_error_does_not_expose_api_key_in_url():
    class UrlLeakingResponse(FakeResponse):
        def raise_for_status(self):
            raise RuntimeError(
                "429 Client Error for url: "
                "https://api.oddspapi.io/v4/fixtures?apiKey=secret&sportId=10"
            )

    client = OddsPapiClient(
        base_url="https://api.oddspapi.io/v4",
        api_key="secret",
        session=FakeSession([UrlLeakingResponse({})]),
    )

    with pytest.raises(OddsPapiApiError) as exc_info:
        client.get("fixtures")

    assert "secret" not in str(exc_info.value)
    assert "apiKey" not in str(exc_info.value)

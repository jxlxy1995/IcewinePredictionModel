import pytest

from icewine_prediction.sources.zqcf918_client import (
    ZQCF918Client,
    ZQCF918ClientError,
    ZQCF918TimelinePayload,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json, timeout, headers):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        return FakeResponse(self.payload)


def _success_payload():
    return {
        "code": 1,
        "success": True,
        "msg": "请求成功",
        "data": {
            "rollList": [{"c": "1.91", "d": "-0.5", "e": "1.95"}],
            "indexList": [],
            "breakfastList": [],
        },
    }


def test_fetch_asian_timeline_posts_expected_body():
    fake_session = FakeSession(_success_payload())
    client = ZQCF918Client(base_url="https://example.test", session=fake_session, timeout_seconds=12)

    payload = client.fetch_asian_timeline("4460916")

    assert isinstance(payload, ZQCF918TimelinePayload)
    assert payload.market == "asian_handicap"
    assert payload.rows == [{"c": "1.91", "d": "-0.5", "e": "1.95"}]
    assert (
        fake_session.calls[0]["url"]
        == "https://example.test/new/match/v11/indexNumber/getAsianIndexNumberListByH5"
    )
    assert fake_session.calls[0]["json"] == {"params": {"matchId": "4460916", "companyId": "87"}}
    assert fake_session.calls[0]["timeout"] == 12


def test_fetch_all_timelines_returns_three_markets():
    fake_session = FakeSession(_success_payload())
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    payloads = client.fetch_all_timelines("4460916")

    assert [payload.market for payload in payloads] == [
        "asian_handicap",
        "total_goals",
        "match_winner",
    ]
    assert len(fake_session.calls) == 3


def test_non_success_response_raises_client_error():
    fake_session = FakeSession({"code": 0, "success": False, "msg": "blocked", "data": None})
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    with pytest.raises(ZQCF918ClientError, match="blocked"):
        client.fetch_asian_timeline("4460916")


def test_fetch_realtime_matches_reads_score_list_candidates():
    fake_session = FakeSession(
        {
            "code": 1,
            "success": True,
            "data": {
                "data1": [
                    {
                        "ID": 4460916,
                        "LName": "世界杯",
                        "HName": "厄瓜多尔",
                        "GName": "德国",
                        "MatchTime": "2026-06-26 04:00:00",
                    }
                ],
                "data2": [],
            },
        }
    )
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    matches = client.fetch_score_matches(type_id=1)

    assert matches == [
        {
            "ID": 4460916,
            "LName": "世界杯",
            "HName": "厄瓜多尔",
            "GName": "德国",
            "MatchTime": "2026-06-26 04:00:00",
        }
    ]
    assert fake_session.calls[0]["url"] == "https://example.test/new/website/real/time/getYPDX"
    assert fake_session.calls[0]["json"] == {"params": {"type": 1}}

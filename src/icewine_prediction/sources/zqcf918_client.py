from dataclasses import dataclass
from typing import Any

import requests


ZQCF918_BASE_URL = "https://www.zqcf918.com"
ZQCF918_PINNACLE_COMPANY_ID = "87"


class ZQCF918ClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZQCF918TimelinePayload:
    market: str
    rows: list[dict[str, Any]]
    raw_payload: dict[str, Any]


class ZQCF918Client:
    ENDPOINTS = {
        "asian_handicap": "/new/match/v11/indexNumber/getAsianIndexNumberListByH5",
        "total_goals": "/new/match/v11/indexNumber/getBallIndexNumberListByH5",
        "match_winner": "/new/match/v11/indexNumber/getEuropeIndexNumberListByH5",
    }

    def __init__(
        self,
        *,
        base_url: str = ZQCF918_BASE_URL,
        company_id: str = ZQCF918_PINNACLE_COMPANY_ID,
        timeout_seconds: float = 20,
        session: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.company_id = str(company_id)
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def fetch_all_timelines(self, match_id: str) -> list[ZQCF918TimelinePayload]:
        return [
            self.fetch_timeline(match_id, "asian_handicap"),
            self.fetch_timeline(match_id, "total_goals"),
            self.fetch_timeline(match_id, "match_winner"),
        ]

    def fetch_asian_timeline(self, match_id: str) -> ZQCF918TimelinePayload:
        return self.fetch_timeline(match_id, "asian_handicap")

    def fetch_timeline(self, match_id: str, market: str) -> ZQCF918TimelinePayload:
        endpoint = self.ENDPOINTS[market]
        payload = self._post_json(
            endpoint,
            body={"params": {"matchId": str(match_id), "companyId": self.company_id}},
            referer=f"{self.base_url}/zsDetail?matchId={match_id}&companyId={self.company_id}&type=0",
        )
        if payload.get("code") != 1 or payload.get("success") is not True:
            raise ZQCF918ClientError(str(payload.get("msg") or "zqcf918 request failed"))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ZQCF918ClientError("zqcf918 response missing data")
        return ZQCF918TimelinePayload(
            market=market,
            rows=_collect_rows(data, ("rollList", "indexList", "breakfastList")),
            raw_payload=payload,
        )

    def fetch_score_matches(self, *, type_id: int = 1) -> list[dict[str, Any]]:
        payload = self._post_json(
            "/new/website/real/time/getYPDX",
            body={"params": {"type": type_id}},
            referer=f"{self.base_url}/score",
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ZQCF918ClientError(str(payload.get("msg") or "zqcf918 score list failed"))
        return _collect_rows(data, ("data1", "data2"))

    def _post_json(self, endpoint: str, *, body: dict[str, Any], referer: str) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}{endpoint}",
            json=body,
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": referer,
                "User-Agent": "Mozilla/5.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ZQCF918ClientError("zqcf918 response is not an object")
        return payload


def _collect_rows(data: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        value = data.get(key) or []
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows

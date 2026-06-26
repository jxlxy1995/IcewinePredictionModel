# zqcf918 Odds Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zqcf918 as a supplemental Pinnacle historical odds source with match ID management, manual/batch sync controls, and automatic fallback after The Odds API failures.

**Architecture:** Keep zqcf918 isolated as a new source module pair: an HTTP client that fetches timelines and a mapper that converts timelines into existing `HistoricalOddsSnapshotInput` rows. Store zqcf918 match IDs in existing `OddsSourceMatch`, store odds in existing historical odds tables with `source_name=zqcf918` and `bookmaker=pinnacle`, and wire zqcf918 into source priority after oddspapi Pinnacle and before oddspapi SBOBet.

**Tech Stack:** Python 3, SQLAlchemy, FastAPI, pytest, React, TypeScript, Vitest, existing historical odds services.

---

## File Structure

- Create `src/icewine_prediction/sources/zqcf918_client.py`
  - HTTP-only client for zqcf918 timeline endpoints.
- Create `src/icewine_prediction/sources/zqcf918_odds_mapper.py`
  - Pure mapper from zqcf918 JSON timelines to `HistoricalOddsSnapshotInput`.
- Create `src/icewine_prediction/zqcf918_match_service.py`
  - `OddsSourceMatch` read/upsert/discovery orchestration helpers.
- Create `src/icewine_prediction/zqcf918_sync_service.py`
  - Fetch/map/store zqcf918 odds and update per-match source status.
- Create `src/icewine_prediction/zqcf918_comparison_service.py`
  - Completed-match comparison report between zqcf918 and existing trusted source rows.
- Modify `src/icewine_prediction/odds_provider_selection_service.py`
  - Add zqcf918 source constant, trusted priority, and source labels.
- Modify `src/icewine_prediction/match_odds_sync_service.py`
  - Add zqcf918 automatic fallback between The Odds API and SBOBet.
- Modify `src/icewine_prediction/match_list_workspace_service.py`
  - Add zqcf918 match ID metadata to match detail payload source.
- Modify `src/icewine_prediction/web_api.py`
  - Add zqcf918 match ID edit and zqcf918 sync endpoints.
- Modify `web/src/types.ts`
  - Add zqcf918 match ID fields and payload/result types.
- Modify `web/src/apiClient.ts`
  - Add API client functions.
- Modify `web/src/components/MatchListTable.tsx`
  - Add single-match zqcf918 odds action button.
- Modify `web/src/pages/DashboardPage.tsx`
  - Add batch buttons, detail editor, and handlers.
- Create tests:
  - `tests/test_zqcf918_client.py`
  - `tests/test_zqcf918_odds_mapper.py`
  - `tests/test_zqcf918_match_service.py`
  - `tests/test_zqcf918_sync_service.py`
  - `tests/test_zqcf918_comparison_service.py`
- Modify existing tests:
  - `tests/test_odds_provider_selection_service.py`
  - `tests/test_match_odds_sync_service.py`
  - `tests/test_match_list_workspace_service.py`
  - `tests/test_web_console_api.py`
  - `web/src/apiClient.test.ts`

---

### Task 1: Source Priority and Labels

**Files:**
- Modify: `src/icewine_prediction/odds_provider_selection_service.py`
- Modify: `tests/test_odds_provider_selection_service.py`

- [ ] **Step 1: Write failing source-priority tests**

Add tests to `tests/test_odds_provider_selection_service.py`:

```python
from datetime import datetime
from decimal import Decimal

from icewine_prediction.models import HistoricalOddsSnapshot
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    PINNACLE_BOOKMAKER,
    SBOBET_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    TRUSTED_SNAPSHOT_PRIORITY,
    ZQCF918_SOURCE_NAME,
    filter_priority_trusted_snapshots,
    source_label_for_snapshots,
)


def _snapshot(match_id: int, source_name: str, bookmaker: str = PINNACLE_BOOKMAKER) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-{match_id}",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"{source_name}-{bookmaker}-ah",
        market_name="Asian Handicap",
        market_line=Decimal("-0.50"),
        outcome_side="home",
        odds=Decimal("1.900"),
        snapshot_time=datetime(2026, 6, 26, 10, 0),
        period="full_time",
    )


def test_trusted_snapshot_priority_places_zqcf918_before_sbobet():
    assert TRUSTED_SNAPSHOT_PRIORITY == (
        (THE_ODDS_API_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ODDSPAPI_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER),
        (ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER),
    )


def test_filter_priority_trusted_snapshots_prefers_zqcf918_over_sbobet():
    selected = filter_priority_trusted_snapshots(
        [
            _snapshot(1, ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER),
            _snapshot(1, ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER),
        ]
    )

    assert [(row.source_name, row.bookmaker) for row in selected] == [
        (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER)
    ]


def test_source_label_includes_zqcf918_pinnacle():
    assert source_label_for_snapshots([_snapshot(1, ZQCF918_SOURCE_NAME)]) == "zqcf918_pinnacle_historical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_odds_provider_selection_service.py -q
```

Expected: FAIL because `ZQCF918_SOURCE_NAME` is not defined and zqcf918 is not in priority.

- [ ] **Step 3: Implement source constants and labels**

Modify `src/icewine_prediction/odds_provider_selection_service.py`:

```python
ODDSPAPI_SOURCE_NAME = "oddspapi"
THE_ODDS_API_SOURCE_NAME = "the_odds_api"
ZQCF918_SOURCE_NAME = "zqcf918"
PINNACLE_BOOKMAKER = "pinnacle"
SBOBET_BOOKMAKER = "sbobet"
PINNACLE_SOURCE_PRIORITY = (
    THE_ODDS_API_SOURCE_NAME,
    ODDSPAPI_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)
TRUSTED_SNAPSHOT_PRIORITY = (
    (THE_ODDS_API_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ODDSPAPI_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER),
    (ODDSPAPI_SOURCE_NAME, SBOBET_BOOKMAKER),
)
```

Update `source_label_for_snapshots`:

```python
    if (ZQCF918_SOURCE_NAME, PINNACLE_BOOKMAKER) in source_bookmakers:
        return "zqcf918_pinnacle_historical"
```

Place the new branch after oddspapi Pinnacle and before oddspapi SBOBet.

- [ ] **Step 4: Run source-priority tests**

Run:

```bash
pytest tests/test_odds_provider_selection_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/odds_provider_selection_service.py tests/test_odds_provider_selection_service.py
git commit -m "feat: add zqcf918 trusted odds priority"
```

---

### Task 2: zqcf918 HTTP Client

**Files:**
- Create: `src/icewine_prediction/sources/zqcf918_client.py`
- Create: `tests/test_zqcf918_client.py`

- [ ] **Step 1: Write failing client tests**

Create `tests/test_zqcf918_client.py`:

```python
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
        "msg": "璇锋眰鎴愬姛",
        "data": {"rollList": [{"c": "1.91", "d": "-0.5", "e": "1.95"}], "indexList": [], "breakfastList": []},
    }


def test_fetch_asian_timeline_posts_expected_body():
    fake_session = FakeSession(_success_payload())
    client = ZQCF918Client(base_url="https://example.test", session=fake_session, timeout_seconds=12)

    payload = client.fetch_asian_timeline("4460916")

    assert isinstance(payload, ZQCF918TimelinePayload)
    assert payload.market == "asian_handicap"
    assert payload.rows == [{"c": "1.91", "d": "-0.5", "e": "1.95"}]
    assert fake_session.calls[0]["url"] == "https://example.test/new/match/v11/indexNumber/getAsianIndexNumberListByH5"
    assert fake_session.calls[0]["json"] == {"params": {"matchId": "4460916", "companyId": "87"}}
    assert fake_session.calls[0]["timeout"] == 12


def test_fetch_all_timelines_returns_three_markets():
    fake_session = FakeSession(_success_payload())
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    payloads = client.fetch_all_timelines("4460916")

    assert [payload.market for payload in payloads] == ["asian_handicap", "total_goals", "match_winner"]
    assert len(fake_session.calls) == 3


def test_non_success_response_raises_client_error():
    fake_session = FakeSession({"code": 0, "success": False, "msg": "blocked", "data": None})
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    with pytest.raises(ZQCF918ClientError, match="blocked"):
        client.fetch_asian_timeline("4460916")
```

- [ ] **Step 2: Run client tests to verify they fail**

Run:

```bash
pytest tests/test_zqcf918_client.py -q
```

Expected: FAIL because `zqcf918_client.py` does not exist.

- [ ] **Step 3: Implement the client**

Create `src/icewine_prediction/sources/zqcf918_client.py`:

```python
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
        response = self.session.post(
            f"{self.base_url}{endpoint}",
            json={"params": {"matchId": str(match_id), "companyId": self.company_id}},
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/zsDetail?matchId={match_id}&companyId={self.company_id}&type=0",
                "User-Agent": "Mozilla/5.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("code") != 1 or payload.get("success") is not True:
            raise ZQCF918ClientError(str(payload.get("msg") or "zqcf918 request failed"))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ZQCF918ClientError("zqcf918 response missing data")
        rows: list[dict[str, Any]] = []
        for key in ("rollList", "indexList", "breakfastList"):
            value = data.get(key) or []
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        return ZQCF918TimelinePayload(market=market, rows=rows, raw_payload=payload)
```

- [ ] **Step 4: Run client tests**

Run:

```bash
pytest tests/test_zqcf918_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/sources/zqcf918_client.py tests/test_zqcf918_client.py
git commit -m "feat: add zqcf918 timeline client"
```

---

### Task 3: zqcf918 Odds Mapper

**Files:**
- Create: `src/icewine_prediction/sources/zqcf918_odds_mapper.py`
- Create: `tests/test_zqcf918_odds_mapper.py`

- [ ] **Step 1: Write failing mapper tests**

Create `tests/test_zqcf918_odds_mapper.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.odds_provider_selection_service import PINNACLE_BOOKMAKER, ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918TimelinePayload
from icewine_prediction.sources.zqcf918_odds_mapper import map_zqcf918_timelines


def test_maps_asian_total_and_match_winner_rows():
    payloads = [
        ZQCF918TimelinePayload(
            market="asian_handicap",
            rows=[{"c": "1.91", "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:00:00Z"}],
            raw_payload={},
        ),
        ZQCF918TimelinePayload(
            market="total_goals",
            rows=[{"c": "1.88", "d": "2.5", "e": "2.02", "changeTime": "2026-06-26T10:05:00Z"}],
            raw_payload={},
        ),
        ZQCF918TimelinePayload(
            market="match_winner",
            rows=[{"c1": "2.40", "c2": "3.20", "c3": "2.90", "changeTime": "2026-06-26T10:10:00Z"}],
            raw_payload={},
        ),
    ]

    snapshots = map_zqcf918_timelines(match_id=123, source_fixture_id="4460916", payloads=payloads)

    assert len(snapshots) == 7
    assert {(row.market_type, row.outcome_side) for row in snapshots} == {
        ("asian_handicap", "home"),
        ("asian_handicap", "away"),
        ("total_goals", "over"),
        ("total_goals", "under"),
        ("match_winner", "home"),
        ("match_winner", "draw"),
        ("match_winner", "away"),
    }
    asian_home = next(row for row in snapshots if row.market_type == "asian_handicap" and row.outcome_side == "home")
    assert asian_home.source_name == ZQCF918_SOURCE_NAME
    assert asian_home.bookmaker == PINNACLE_BOOKMAKER
    assert asian_home.market_line == Decimal("-0.50")
    assert asian_home.odds == Decimal("1.910")
    assert asian_home.snapshot_time == datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("UTC"))


def test_skips_sealed_and_malformed_rows():
    payloads = [
        ZQCF918TimelinePayload(
            market="asian_handicap",
            rows=[
                {"c": "1.91", "d": "-0.5", "e": "1.95", "isFeng2": True, "changeTime": "2026-06-26T10:00:00Z"},
                {"c": "灏?, "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:01:00Z"},
                {"c": "1.92", "d": "-0.25", "e": "1.96", "changeTimeStr": "2026-06-26 18:02:00"},
            ],
            raw_payload={},
        )
    ]

    snapshots = map_zqcf918_timelines(match_id=123, source_fixture_id="4460916", payloads=payloads)

    assert len(snapshots) == 2
    assert {row.outcome_side for row in snapshots} == {"home", "away"}
    assert snapshots[0].snapshot_time.tzinfo is not None
```

- [ ] **Step 2: Run mapper tests to verify they fail**

Run:

```bash
pytest tests/test_zqcf918_odds_mapper.py -q
```

Expected: FAIL because mapper does not exist.

- [ ] **Step 3: Implement mapper**

Create `src/icewine_prediction/sources/zqcf918_odds_mapper.py`:

```python
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from typing import Any
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import HistoricalOddsSnapshotInput
from icewine_prediction.odds_provider_selection_service import PINNACLE_BOOKMAKER, ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918TimelinePayload


UTC = ZoneInfo("UTC")
BEIJING = ZoneInfo("Asia/Shanghai")


def map_zqcf918_timelines(
    *,
    match_id: int,
    source_fixture_id: str,
    payloads: list[ZQCF918TimelinePayload],
) -> list[HistoricalOddsSnapshotInput]:
    snapshots: list[HistoricalOddsSnapshotInput] = []
    for payload in payloads:
        for row in payload.rows:
            if _is_sealed(row):
                continue
            if payload.market == "asian_handicap":
                snapshots.extend(_map_two_way(match_id, source_fixture_id, payload.market, "Asian Handicap", row, "home", "away"))
            elif payload.market == "total_goals":
                snapshots.extend(_map_two_way(match_id, source_fixture_id, payload.market, "Total Goals", row, "over", "under"))
            elif payload.market == "match_winner":
                snapshots.extend(_map_match_winner(match_id, source_fixture_id, row))
    return snapshots


def _map_two_way(
    match_id: int,
    source_fixture_id: str,
    market_type: str,
    market_name: str,
    row: dict[str, Any],
    left_side: str,
    right_side: str,
) -> list[HistoricalOddsSnapshotInput]:
    line = _decimal(row.get("d"), places="0.01")
    left_odds = _decimal(row.get("c"), places="0.001")
    right_odds = _decimal(row.get("e"), places="0.001")
    snapshot_time = _parse_time(row)
    if line is None or left_odds is None or right_odds is None or snapshot_time is None:
        return []
    return [
        _snapshot(match_id, source_fixture_id, market_type, market_name, line, left_side, left_odds, snapshot_time, row),
        _snapshot(match_id, source_fixture_id, market_type, market_name, line, right_side, right_odds, snapshot_time, row),
    ]


def _map_match_winner(match_id: int, source_fixture_id: str, row: dict[str, Any]) -> list[HistoricalOddsSnapshotInput]:
    snapshot_time = _parse_time(row)
    odds_by_side = {
        "home": _decimal(row.get("c1"), places="0.001"),
        "draw": _decimal(row.get("c2"), places="0.001"),
        "away": _decimal(row.get("c3"), places="0.001"),
    }
    if snapshot_time is None or any(value is None for value in odds_by_side.values()):
        return []
    return [
        _snapshot(match_id, source_fixture_id, "match_winner", "Match Winner", Decimal("0.00"), side, odds, snapshot_time, row)
        for side, odds in odds_by_side.items()
        if odds is not None
    ]


def _snapshot(
    match_id: int,
    source_fixture_id: str,
    market_type: str,
    market_name: str,
    market_line: Decimal,
    outcome_side: str,
    odds: Decimal,
    snapshot_time: datetime,
    row: dict[str, Any],
) -> HistoricalOddsSnapshotInput:
    return HistoricalOddsSnapshotInput(
        match_id=match_id,
        source_name=ZQCF918_SOURCE_NAME,
        source_fixture_id=source_fixture_id,
        bookmaker=PINNACLE_BOOKMAKER,
        market_type=market_type,
        market_id=f"{source_fixture_id}:{market_type}:{market_line}:{outcome_side}",
        market_name=market_name,
        market_line=market_line,
        outcome_side=outcome_side,
        odds=odds,
        snapshot_time=snapshot_time,
        period="full_time",
        raw_payload=json.dumps(row, ensure_ascii=False, sort_keys=True),
    )


def _is_sealed(row: dict[str, Any]) -> bool:
    if row.get("isFeng2") is True:
        return True
    return any(str(value).strip() in {"", "灏?, "-", "None"} for value in (row.get("c"), row.get("d"), row.get("e")))


def _decimal(value: Any, *, places: str) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_time(row: dict[str, Any]) -> datetime | None:
    value = row.get("changeTime")
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    value = row.get("changeTimeStr")
    if value:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING).astimezone(UTC)
        except ValueError:
            return None
    return None
```

- [ ] **Step 4: Run mapper tests**

Run:

```bash
pytest tests/test_zqcf918_odds_mapper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/sources/zqcf918_odds_mapper.py tests/test_zqcf918_odds_mapper.py
git commit -m "feat: map zqcf918 odds timelines"
```

---

### Task 4: zqcf918 Match ID Service and Match Detail Payload

**Files:**
- Create: `src/icewine_prediction/zqcf918_match_service.py`
- Modify: `src/icewine_prediction/match_list_workspace_service.py`
- Modify: `src/icewine_prediction/web_api.py`
- Create: `tests/test_zqcf918_match_service.py`
- Modify: `tests/test_match_list_workspace_service.py`
- Modify: `tests/test_web_console_api.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_zqcf918_match_service.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.zqcf918_match_service import (
    ZQCF918MatchIdUpdate,
    get_zqcf918_match_id,
    upsert_zqcf918_match_id,
)


def test_upsert_zqcf918_match_id_creates_manual_mapping(session):
    match = _add_match(session)

    result = upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=match.id, source_fixture_id="4460916", reason="manual:web-detail"),
    )

    assert result.source_fixture_id == "4460916"
    assert result.source_name == ZQCF918_SOURCE_NAME
    assert result.match_confidence == Decimal("1.0000")
    assert get_zqcf918_match_id(session, match.id).source_fixture_id == "4460916"


def test_upsert_zqcf918_match_id_updates_existing_mapping(session):
    match = _add_match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id="old",
            matched_at=datetime(2026, 6, 26, tzinfo=ZoneInfo("UTC")),
            match_confidence=Decimal("0.5000"),
            match_reason="auto",
        )
    )
    session.commit()

    upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=match.id, source_fixture_id="4460916", reason="manual:web-detail"),
    )

    rows = session.query(OddsSourceMatch).filter_by(match_id=match.id, source_name=ZQCF918_SOURCE_NAME).all()
    assert len(rows) == 1
    assert rows[0].source_fixture_id == "4460916"


def _add_match(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Home")
    away = Team(canonical_name="Away")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match
```

- [ ] **Step 2: Write failing detail payload test**

Add to `tests/test_web_console_api.py` near the match detail tests:

```python
def test_web_console_api_updates_zqcf918_match_id_in_detail(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Home")
        away = Team(canonical_name="Away")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.commit()
        match_id = match.id

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.put(f"/api/matches/{match_id}/zqcf918-match-id", json={"match_id": "4460916"})
    detail = client.get(f"/api/matches/{match_id}/detail").json()

    assert response.status_code == 200
    assert response.json()["source_fixture_id"] == "4460916"
    assert detail["zqcf918_match_id"] == "4460916"
    assert detail["zqcf918_match_url"].endswith("matchId=4460916&companyId=87&type=0")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/test_zqcf918_match_service.py tests/test_web_console_api.py::test_web_console_api_updates_zqcf918_match_id_in_detail -q
```

Expected: FAIL because service, detail fields, and endpoint do not exist.

- [ ] **Step 4: Implement match ID service**

Create `src/icewine_prediction/zqcf918_match_service.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918_PINNACLE_COMPANY_ID, ZQCF918_BASE_URL


UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class ZQCF918MatchIdUpdate:
    match_id: int
    source_fixture_id: str
    reason: str
    confidence: Decimal = Decimal("1.0000")


def zqcf918_match_url(source_fixture_id: str) -> str:
    return f"{ZQCF918_BASE_URL}/zsDetail?matchId={source_fixture_id}&companyId={ZQCF918_PINNACLE_COMPANY_ID}&type=0"


def get_zqcf918_match_id(session: Session, match_id: int) -> OddsSourceMatch | None:
    return (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match_id, source_name=ZQCF918_SOURCE_NAME)
        .one_or_none()
    )


def upsert_zqcf918_match_id(session: Session, update: ZQCF918MatchIdUpdate) -> OddsSourceMatch:
    if session.get(Match, update.match_id) is None:
        raise ValueError("match not found")
    source_fixture_id = str(update.source_fixture_id).strip()
    if not source_fixture_id.isdigit():
        raise ValueError("zqcf918 match ID must be numeric")
    row = get_zqcf918_match_id(session, update.match_id)
    if row is None:
        row = OddsSourceMatch(
            match_id=update.match_id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id=source_fixture_id,
            matched_at=datetime.now(tz=UTC),
            match_confidence=update.confidence,
            match_reason=update.reason,
        )
        session.add(row)
    else:
        row.source_fixture_id = source_fixture_id
        row.matched_at = datetime.now(tz=UTC)
        row.match_confidence = update.confidence
        row.match_reason = update.reason
    session.commit()
    return row
```

- [ ] **Step 5: Add detail dataclass fields**

Modify `MatchDetail` in `src/icewine_prediction/match_list_workspace_service.py`:

```python
    zqcf918_match_id: str | None
    zqcf918_match_url: str | None
```

Import helpers:

```python
from icewine_prediction.zqcf918_match_service import get_zqcf918_match_id, zqcf918_match_url
```

Inside `build_match_detail`, before `return MatchDetail(...)`:

```python
    zqcf918_source_match = get_zqcf918_match_id(session, match.id)
    zqcf918_source_fixture_id = (
        zqcf918_source_match.source_fixture_id
        if zqcf918_source_match and zqcf918_source_match.source_fixture_id
        else None
    )
```

Add to `MatchDetail(...)`:

```python
        zqcf918_match_id=zqcf918_source_fixture_id,
        zqcf918_match_url=(
            zqcf918_match_url(zqcf918_source_fixture_id)
            if zqcf918_source_fixture_id
            else None
        ),
```

Modify `build_match_detail_payload` in `src/icewine_prediction/web_api.py`:

```python
        "zqcf918_match_id": detail.zqcf918_match_id,
        "zqcf918_match_url": detail.zqcf918_match_url,
```

- [ ] **Step 6: Add match ID edit endpoint**

Import in `src/icewine_prediction/web_api.py`:

```python
from icewine_prediction.zqcf918_match_service import ZQCF918MatchIdUpdate, upsert_zqcf918_match_id
```

Add route near match detail routes:

```python
    @app.put("/api/matches/{match_id}/zqcf918-match-id")
    def update_match_zqcf918_match_id(match_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        source_fixture_id = str(payload.get("match_id") or payload.get("source_fixture_id") or "").strip()
        with session_factory() as session:
            try:
                row = upsert_zqcf918_match_id(
                    session,
                    ZQCF918MatchIdUpdate(
                        match_id=match_id,
                        source_fixture_id=source_fixture_id,
                        reason="manual:web-detail",
                    ),
                )
            except ValueError as error:
                status_code = 404 if str(error) == "match not found" else 400
                raise HTTPException(status_code=status_code, detail=str(error)) from error
        clear_cache_prefix("match-list-workspace")
        return {
            "match_id": row.match_id,
            "source_name": row.source_name,
            "source_fixture_id": row.source_fixture_id,
            "match_confidence": str(row.match_confidence),
            "match_reason": row.match_reason,
        }
```

- [ ] **Step 7: Run backend tests**

Run:

```bash
pytest tests/test_zqcf918_match_service.py tests/test_web_console_api.py::test_web_console_api_updates_zqcf918_match_id_in_detail -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/icewine_prediction/zqcf918_match_service.py src/icewine_prediction/match_list_workspace_service.py src/icewine_prediction/web_api.py tests/test_zqcf918_match_service.py tests/test_web_console_api.py
git commit -m "feat: manage zqcf918 match ids"
```

---

### Task 5: zqcf918 Match ID Discovery and Batch Sync

**Files:**
- Modify: `src/icewine_prediction/sources/zqcf918_client.py`
- Modify: `src/icewine_prediction/zqcf918_match_service.py`
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `tests/test_zqcf918_client.py`
- Modify: `tests/test_zqcf918_match_service.py`
- Modify: `tests/test_web_console_api.py`

- [ ] **Step 1: Write failing client tests for score-list candidates**

Add to `tests/test_zqcf918_client.py`:

```python
def test_fetch_realtime_matches_reads_score_list_candidates():
    fake_session = FakeSession(
        {
            "code": 1,
            "success": True,
            "data": {
                "data1": [
                    {"ID": 4460916, "LName": "世界杯", "HName": "厄瓜多尔", "GName": "德国", "MatchTime": "2026-06-26 04:00:00"}
                ],
                "data2": [],
            },
        }
    )
    client = ZQCF918Client(base_url="https://example.test", session=fake_session)

    matches = client.fetch_score_matches(type_id=1)

    assert matches == [
        {"ID": 4460916, "LName": "世界杯", "HName": "厄瓜多尔", "GName": "德国", "MatchTime": "2026-06-26 04:00:00"}
    ]
    assert fake_session.calls[0]["url"] == "https://example.test/new/website/real/time/getYPDX"
    assert fake_session.calls[0]["json"] == {"params": {"type": 1}}
```

- [ ] **Step 2: Write failing batch match ID service test**

Add to `tests/test_zqcf918_match_service.py`:

```python
from icewine_prediction.zqcf918_match_service import sync_zqcf918_match_ids_for_matches


class FakeDiscoverer:
    def __init__(self):
        self.calls = []

    def discover(self, matches):
        self.calls.append([match.id for match in matches])
        return {matches[0].id: "4460916"}


def test_sync_zqcf918_match_ids_only_targets_missing_mappings(session):
    first = _add_match(session)
    second = _add_match(session)
    upsert_zqcf918_match_id(
        session,
        ZQCF918MatchIdUpdate(match_id=second.id, source_fixture_id="999", reason="manual:web-detail"),
    )
    discoverer = FakeDiscoverer()

    result = sync_zqcf918_match_ids_for_matches(session, [first, second], discoverer=discoverer)

    assert discoverer.calls == [[first.id]]
    assert [item["match_id"] for item in result["success"]] == [first.id]
    assert [item["match_id"] for item in result["skipped"]] == [second.id]
    assert get_zqcf918_match_id(session, first.id).source_fixture_id == "4460916"
```

- [ ] **Step 3: Write failing web endpoint test**

Add to `tests/test_web_console_api.py`:

```python
def test_web_console_api_syncs_filtered_zqcf918_match_ids(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Home")
        away = Team(canonical_name="Away")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.commit()
        match_id = match.id

    calls = []

    def fake_zqcf918_match_id_syncer(match_ids):
        calls.append(match_ids)
        return {"success": [{"match_id": match_id, "message": "matched", "source_fixture_id": "4460916"}], "failed": [], "skipped": [], "requests": 1, "credits": 0}

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            zqcf918_match_id_syncer=fake_zqcf918_match_id_syncer,
        )
    )

    response = client.post(
        "/api/match-list/sync/zqcf918-match-ids",
        json={"start_time": "2026-06-26T00:00:00+08:00", "end_time": "2026-06-27T12:00:00+08:00"},
    )

    assert response.status_code == 200
    assert calls == [[match_id]]
    assert response.json()["report"]["sync_type"] == "zqcf918_match_ids"
```

- [ ] **Step 4: Run match ID sync tests to verify they fail**

Run:

```bash
pytest tests/test_zqcf918_client.py::test_fetch_realtime_matches_reads_score_list_candidates tests/test_zqcf918_match_service.py::test_sync_zqcf918_match_ids_only_targets_missing_mappings tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_match_ids -q
```

Expected: FAIL because candidate list fetching, batch sync service, and route do not exist.

- [ ] **Step 5: Add score-list client method**

Add to `src/icewine_prediction/sources/zqcf918_client.py`:

```python
    def fetch_score_matches(self, *, type_id: int = 1) -> list[dict[str, Any]]:
        response = self.session.post(
            f"{self.base_url}/new/website/real/time/getYPDX",
            json={"params": {"type": type_id}},
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/score",
                "User-Agent": "Mozilla/5.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ZQCF918ClientError(str(payload.get("msg") if isinstance(payload, dict) else "zqcf918 score list failed"))
        rows: list[dict[str, Any]] = []
        for key in ("data1", "data2"):
            value = data.get(key) or []
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        return rows
```

- [ ] **Step 6: Add simple discoverer and batch sync service**

Add to `src/icewine_prediction/zqcf918_match_service.py`:

```python
from typing import Any
from icewine_prediction.sources.zqcf918_client import ZQCF918Client


class ZQCF918MatchDiscoverer:
    def __init__(self, client: ZQCF918Client | None = None) -> None:
        self.client = client or ZQCF918Client()

    def discover(self, matches: list[Match]) -> dict[int, str]:
        candidates = self.client.fetch_score_matches(type_id=1)
        return _match_candidates(matches, candidates)


def sync_zqcf918_match_ids_for_matches(
    session: Session,
    matches: list[Match],
    *,
    discoverer: Any | None = None,
) -> dict[str, list[dict[str, Any]] | int]:
    discoverer = discoverer or ZQCF918MatchDiscoverer()
    target_matches = [match for match in matches if get_zqcf918_match_id(session, match.id) is None]
    skipped = [
        {"match_id": match.id, "message": "zqcf918 match ID already exists"}
        for match in matches
        if match not in target_matches
    ]
    discovered = discoverer.discover(target_matches) if target_matches else {}
    success: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for match in target_matches:
        source_fixture_id = discovered.get(match.id)
        if not source_fixture_id:
            failed.append({"match_id": match.id, "message": "zqcf918 match ID not found"})
            continue
        row = upsert_zqcf918_match_id(
            session,
            ZQCF918MatchIdUpdate(
                match_id=match.id,
                source_fixture_id=source_fixture_id,
                reason="auto:zqcf918-score-list",
                confidence=Decimal("0.9000"),
            ),
        )
        success.append({"match_id": match.id, "message": "zqcf918 match ID synced", "source_fixture_id": row.source_fixture_id})
    return {"success": success, "failed": failed, "skipped": skipped, "requests": 1 if target_matches else 0, "credits": 0}


def _match_candidates(matches: list[Match], candidates: list[dict[str, Any]]) -> dict[int, str]:
    matched: dict[int, str] = {}
    for match in matches:
        for candidate in candidates:
            candidate_id = candidate.get("ID") or candidate.get("id") or candidate.get("matchId")
            if candidate_id is None:
                continue
            if _normalized_team(match.home_team.canonical_name) not in _candidate_text(candidate):
                continue
            if _normalized_team(match.away_team.canonical_name) not in _candidate_text(candidate):
                continue
            matched[match.id] = str(candidate_id)
            break
    return matched


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(_normalized_team(value) for value in candidate.values() if isinstance(value, str))


def _normalized_team(value: str) -> str:
    return value.lower().replace(" ", "")
```

This first matcher is intentionally conservative. If the candidate rows do not expose stable team-name fields for a match, leave that match in the failed list and rely on the manual match ID editor.

- [ ] **Step 7: Add match ID sync API route**

Modify `create_web_app` signature in `src/icewine_prediction/web_api.py`:

```python
    zqcf918_match_id_syncer: Callable[[list[int]], dict[str, Any] | str] | None = None,
```

Initialize:

```python
    zqcf918_match_id_syncer = zqcf918_match_id_syncer or _run_zqcf918_match_id_sync
```

Add route near match-list sync routes:

```python
    @app.post("/api/match-list/sync/zqcf918-match-ids")
    def sync_match_list_zqcf918_match_ids(payload: dict[str, Any]) -> dict[str, Any]:
        return _sync_match_list_from_payload(
            payload=payload,
            sync_type="zqcf918_match_ids",
            syncer=zqcf918_match_id_syncer,
            cache_prefixes=("match-list-workspace",),
        )
```

Add module-level runner:

```python
def _run_zqcf918_match_id_sync(match_ids: list[int]) -> dict[str, Any]:
    from icewine_prediction.zqcf918_match_service import sync_zqcf918_match_ids_for_matches

    with _open_session_for_web_sync() as session:
        matches = session.query(Match).filter(Match.id.in_(match_ids)).all()
        return sync_zqcf918_match_ids_for_matches(session, matches)
```

- [ ] **Step 8: Run match ID sync tests**

Run:

```bash
pytest tests/test_zqcf918_client.py::test_fetch_realtime_matches_reads_score_list_candidates tests/test_zqcf918_match_service.py::test_sync_zqcf918_match_ids_only_targets_missing_mappings tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_match_ids -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/icewine_prediction/sources/zqcf918_client.py src/icewine_prediction/zqcf918_match_service.py src/icewine_prediction/web_api.py tests/test_zqcf918_client.py tests/test_zqcf918_match_service.py tests/test_web_console_api.py
git commit -m "feat: sync zqcf918 match ids"
```

---

### Task 6: zqcf918 Odds Sync Service

**Files:**
- Create: `src/icewine_prediction/zqcf918_sync_service.py`
- Create: `tests/test_zqcf918_sync_service.py`

- [ ] **Step 1: Write failing sync service tests**

Create `tests/test_zqcf918_sync_service.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import PINNACLE_BOOKMAKER, ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918TimelinePayload
from icewine_prediction.zqcf918_sync_service import run_zqcf918_sync_for_session


class FakeZQCF918Client:
    def __init__(self):
        self.calls = []

    def fetch_all_timelines(self, match_id):
        self.calls.append(match_id)
        return [
            ZQCF918TimelinePayload(
                market="asian_handicap",
                rows=[{"c": "1.91", "d": "-0.5", "e": "1.95", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
            ZQCF918TimelinePayload(
                market="total_goals",
                rows=[{"c": "1.88", "d": "2.5", "e": "2.02", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
            ZQCF918TimelinePayload(
                market="match_winner",
                rows=[{"c1": "2.40", "c2": "3.20", "c3": "2.90", "changeTime": "2026-06-26T10:00:00Z"}],
                raw_payload={},
            ),
        ]


def test_run_zqcf918_sync_stores_pinnacle_snapshots(session):
    match = _add_match(session)
    _add_source_match(session, match.id, "4460916")
    client = FakeZQCF918Client()

    result = run_zqcf918_sync_for_session(session=session, match_ids=[match.id], client=client)

    assert client.calls == ["4460916"]
    assert [item["match_id"] for item in result["success"]] == [match.id]
    assert result["failed"] == []
    assert result["requests"] == 3
    assert result["credits"] == 0
    snapshots = session.query(HistoricalOddsSnapshot).filter_by(match_id=match.id).all()
    assert len(snapshots) == 7
    assert {row.source_name for row in snapshots} == {ZQCF918_SOURCE_NAME}
    assert {row.bookmaker for row in snapshots} == {PINNACLE_BOOKMAKER}


def test_run_zqcf918_sync_skips_missing_match_id(session):
    match = _add_match(session)

    result = run_zqcf918_sync_for_session(session=session, match_ids=[match.id], client=FakeZQCF918Client())

    assert result["success"] == []
    assert [item["match_id"] for item in result["skipped"]] == [match.id]


def _add_match(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Home")
    away = Team(canonical_name="Away")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="scheduled",
    )
    session.add(match)
    session.commit()
    return match


def _add_source_match(session, match_id, source_fixture_id):
    session.add(
        OddsSourceMatch(
            match_id=match_id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id=source_fixture_id,
            matched_at=datetime(2026, 6, 26, tzinfo=ZoneInfo("UTC")),
            match_confidence=Decimal("1.0000"),
            match_reason="manual",
        )
    )
    session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_zqcf918_sync_service.py -q
```

Expected: FAIL because sync service does not exist.

- [ ] **Step 3: Implement sync service**

Create `src/icewine_prediction/zqcf918_sync_service.py`:

```python
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.historical_odds_service import (
    store_historical_odds_raw_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import Match
from icewine_prediction.sources.zqcf918_client import ZQCF918Client
from icewine_prediction.sources.zqcf918_odds_mapper import map_zqcf918_timelines
from icewine_prediction.zqcf918_match_service import get_zqcf918_match_id


UTC = ZoneInfo("UTC")
SyncResultPayload = dict[str, list[dict[str, Any]] | int]


def run_zqcf918_sync_for_session(
    *,
    session: Session,
    match_ids: list[int] | set[int],
    client: ZQCF918Client | Any | None = None,
) -> SyncResultPayload:
    client = client or ZQCF918Client()
    matches = session.query(Match).filter(Match.id.in_(list(match_ids))).all()
    matches_by_id = {match.id: match for match in matches}
    success: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    requests = 0

    for match_id in match_ids:
        match = matches_by_id.get(match_id)
        if match is None:
            skipped.append({"match_id": match_id, "message": "match not found"})
            continue
        source_match = get_zqcf918_match_id(session, match.id)
        if source_match is None or not source_match.source_fixture_id:
            skipped.append({"match_id": match.id, "message": "missing zqcf918 match ID"})
            continue
        try:
            payloads = client.fetch_all_timelines(source_match.source_fixture_id)
            requests += len(payloads)
            mapped = map_zqcf918_timelines(
                match_id=match.id,
                source_fixture_id=source_match.source_fixture_id,
                payloads=payloads,
            )
            if not mapped:
                source_match.historical_odds_status = "empty"
                source_match.historical_odds_checked_at = datetime.now(tz=UTC)
                source_match.historical_odds_error = "no usable zqcf918 odds"
                session.commit()
                failed.append({"match_id": match.id, "message": "no usable zqcf918 odds"})
                continue
            raw_result = store_historical_odds_raw_snapshots(
                session,
                mapped,
                kickoff_time=match.kickoff_time,
                max_snapshots_per_match=450,
                max_snapshots_per_market_type=150,
            )
            store_result = store_historical_odds_snapshots(
                session,
                mapped,
                kickoff_time=match.kickoff_time,
                max_snapshots_per_match=200,
                max_snapshots_per_market_type=50,
                execution_timepoint_source_snapshots=mapped,
            )
            source_match.historical_odds_status = "stored"
            source_match.historical_odds_checked_at = datetime.now(tz=UTC)
            source_match.historical_odds_error = None
            session.commit()
            success.append(
                {
                    "match_id": match.id,
                    "message": "zqcf918 odds synced",
                    "created_count": store_result.inserted_count,
                    "updated_count": 0,
                    "skipped_count": raw_result.skipped_duplicate_count + store_result.skipped_duplicate_count,
                    "requests_used": len(payloads),
                    "source_fixture_id": source_match.source_fixture_id,
                    "snapshot_count": len(mapped),
                }
            )
        except Exception as error:
            source_match.historical_odds_status = "failed"
            source_match.historical_odds_checked_at = datetime.now(tz=UTC)
            source_match.historical_odds_error = str(error)
            session.commit()
            failed.append({"match_id": match.id, "message": str(error)})

    return {"success": success, "failed": failed, "skipped": skipped, "requests": requests, "credits": 0}
```

- [ ] **Step 4: Run sync service tests**

Run:

```bash
pytest tests/test_zqcf918_sync_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/zqcf918_sync_service.py tests/test_zqcf918_sync_service.py
git commit -m "feat: sync zqcf918 historical odds"
```

---

### Task 7: Automatic Fallback Integration

**Files:**
- Modify: `src/icewine_prediction/match_odds_sync_service.py`
- Modify: `tests/test_match_odds_sync_service.py`

- [ ] **Step 1: Write failing fallback tests**

Add to `tests/test_match_odds_sync_service.py`:

```python
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME


def test_run_match_odds_sync_falls_back_to_zqcf918_before_sbobet(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild",
        country_or_region="Iceland",
        source_league_id="164",
    )
    zqcf918_calls = []
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_zqcf918_sync(**kwargs):
        zqcf918_calls.append(kwargs)
        session.add(_snapshot(match_id=match.id, source_name=ZQCF918_SOURCE_NAME, odds=Decimal("1.91")))
        session.commit()
        return {"success": [{"match_id": match.id}], "failed": [], "skipped": [], "requests": 3, "credits": 0}

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert zqcf918_calls
    assert zqcf918_calls[0]["match_ids"] == {match.id}
    assert oddspapi_calls == []
    assert result["requests"] == 5
    assert result["credits"] == 60
    assert _success_match_ids(result) == [match.id]


def test_run_match_odds_sync_uses_sbobet_when_zqcf918_has_no_odds(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild",
        country_or_region="Iceland",
        source_league_id="164",
    )
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_zqcf918_sync(**kwargs):
        return {"success": [], "failed": [{"match_id": match.id, "message": "empty"}], "skipped": [], "requests": 3, "credits": 0}

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        session.add(_snapshot(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME, bookmaker="sbobet", odds=Decimal("1.90")))
        session.commit()
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert oddspapi_calls
    assert oddspapi_calls[0]["bookmaker"] == "sbobet"
    assert result["requests"] == 10
    assert _success_match_ids(result) == [match.id]
```

- [ ] **Step 2: Run fallback tests to verify they fail**

Run:

```bash
pytest tests/test_match_odds_sync_service.py -q
```

Expected: FAIL because `run_match_odds_sync_for_session` does not accept `zqcf918_syncer`.

- [ ] **Step 3: Implement zqcf918 fallback hook**

Modify imports in `src/icewine_prediction/match_odds_sync_service.py`:

```python
from icewine_prediction.zqcf918_sync_service import run_zqcf918_sync_for_session
```

Modify signature:

```python
    zqcf918_syncer: Callable[..., Any] = run_zqcf918_sync_for_session,
```

After The Odds API provider run and before `_sbobet_fallback_match_ids`, add:

```python
            if selected_provider == MatchOddsSyncProvider.THE_ODDS_API:
                zqcf918_match_ids = _zqcf918_fallback_match_ids(session, matches, season_match_ids)
                if zqcf918_match_ids:
                    zqcf918_result = zqcf918_syncer(session=session, match_ids=zqcf918_match_ids)
                    requests_used += int(zqcf918_result.get("requests", 0) or 0)
                    credits_used += int(zqcf918_result.get("credits", 0) or 0)
                    for item in zqcf918_result.get("failed", []):
                        run_errors[int(item["match_id"])] = str(item.get("message") or "zqcf918 failed")
                    for item in zqcf918_result.get("skipped", []):
                        run_errors[int(item["match_id"])] = str(item.get("message") or "zqcf918 skipped")
```

Add helper:

```python
def _zqcf918_fallback_match_ids(
    session: Session,
    matches: list[Match],
    season_match_ids: set[int],
) -> set[int]:
    fallback_ids = set()
    for match in matches:
        if match.id not in season_match_ids:
            continue
        if has_trusted_historical_odds(session, match.id):
            continue
        fallback_ids.add(match.id)
    return fallback_ids
```

Leave SBOBet fallback after this block so it only runs for matches still missing trusted odds.

- [ ] **Step 4: Run match odds sync tests**

Run:

```bash
pytest tests/test_match_odds_sync_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/match_odds_sync_service.py tests/test_match_odds_sync_service.py
git commit -m "feat: add zqcf918 odds fallback"
```

---

### Task 8: Web API Endpoints for zqcf918 Sync

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `tests/test_web_console_api.py`

- [ ] **Step 1: Write failing API endpoint tests**

Add to `tests/test_web_console_api.py`:

```python
def test_web_console_api_syncs_single_zqcf918_odds(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Home")
        away = Team(canonical_name="Away")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.commit()
        match_id = match.id

    calls = []

    def fake_zqcf918_syncer(match_ids):
        calls.append(match_ids)
        return {"success": [{"match_id": match_id, "message": "ok"}], "failed": [], "skipped": [], "requests": 3, "credits": 0}

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            zqcf918_odds_syncer=fake_zqcf918_syncer,
        )
    )

    response = client.post(f"/api/matches/{match_id}/sync/zqcf918-odds", json={})

    assert response.status_code == 200
    assert calls == [[match_id]]
    assert response.json()["report"]["sync_type"] == "zqcf918_odds"


def test_web_console_api_syncs_filtered_zqcf918_odds(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Home")
        away = Team(canonical_name="Away")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.commit()
        match_id = match.id

    calls = []

    def fake_zqcf918_syncer(match_ids):
        calls.append(match_ids)
        return {"success": [{"match_id": match_id, "message": "ok"}], "failed": [], "skipped": [], "requests": 3, "credits": 0}

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            zqcf918_odds_syncer=fake_zqcf918_syncer,
        )
    )

    response = client.post(
        "/api/match-list/sync/zqcf918-odds",
        json={"start_time": "2026-06-26T00:00:00+08:00", "end_time": "2026-06-27T12:00:00+08:00"},
    )

    assert response.status_code == 200
    assert calls == [[match_id]]
    assert response.json()["report"]["target_count"] == 1
```

- [ ] **Step 2: Run endpoint tests to verify they fail**

Run:

```bash
pytest tests/test_web_console_api.py::test_web_console_api_syncs_single_zqcf918_odds tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_odds -q
```

Expected: FAIL because `create_web_app` has no `zqcf918_odds_syncer` parameter and routes do not exist.

- [ ] **Step 3: Add dependency injection and routes**

Modify `create_web_app` signature in `src/icewine_prediction/web_api.py`:

```python
    zqcf918_odds_syncer: Callable[[list[int]], dict[str, Any] | str] | None = None,
```

Initialize:

```python
    zqcf918_odds_syncer = zqcf918_odds_syncer or _run_zqcf918_odds_sync
```

Add routes near existing odds sync routes:

```python
    @app.post("/api/match-list/sync/zqcf918-odds")
    def sync_match_list_zqcf918_odds(payload: dict[str, Any]) -> dict[str, Any]:
        return _sync_match_list_from_payload(
            payload=payload,
            sync_type="zqcf918_odds",
            syncer=zqcf918_odds_syncer,
            cache_prefixes=(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "paper-recommendation-workspace",
            ),
        )

    @app.post("/api/matches/{match_id}/sync/zqcf918-odds")
    def sync_match_zqcf918_odds(match_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return _sync_single_match(
            match_id=match_id,
            sync_type="zqcf918_odds",
            syncer=zqcf918_odds_syncer,
            cache_prefixes=(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "paper-recommendation-workspace",
            ),
        )
```

If `_sync_match_list_from_payload` does not exist, extract the body of `sync_match_list_odds` into that helper:

```python
    def _sync_match_list_from_payload(
        *,
        payload: dict[str, Any],
        sync_type: str,
        syncer: Callable[[list[int]], dict[str, Any] | str],
        cache_prefixes: tuple[str, ...],
    ) -> dict[str, Any]:
        started_at = clock()
        with session_factory() as session:
            matches = _select_sync_matches_from_payload(session, payload, now=clock())
            match_ids = [match.id for match in matches]
            try:
                report = _build_match_sync_report(
                    session=session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    matches=matches,
                    result=syncer(match_ids),
                    display_name_service=display_name_service,
                )
                sync_result = _sync_run_counts_from_report(report)
                run = record_sync_run(
                    session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    status="success",
                    days=0,
                    **sync_result,
                )
                _persist_match_sync_run_items(session, run=run, report=report)
            except Exception as error:
                record_sync_run(
                    session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    status="failed",
                    days=0,
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    requests_used=0,
                    error_message=str(error),
                )
                raise HTTPException(status_code=500, detail=str(error)) from error
            clear_cache_prefix(*cache_prefixes)
            return {"sync_run": build_data_sync_run_payload(run), "report": report}
```

Add module-level default runner:

```python
def _run_zqcf918_odds_sync(match_ids: list[int]) -> dict[str, Any]:
    from icewine_prediction.zqcf918_sync_service import run_zqcf918_sync_for_session

    with _open_session_for_web_sync() as session:
        return run_zqcf918_sync_for_session(session=session, match_ids=match_ids)
```

- [ ] **Step 4: Run API tests**

Run:

```bash
pytest tests/test_web_console_api.py::test_web_console_api_syncs_single_zqcf918_odds tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_odds -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/web_api.py tests/test_web_console_api.py
git commit -m "feat: expose zqcf918 odds sync api"
```

---

### Task 9: Frontend API and UI Controls

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/apiClient.test.ts`
- Modify: `web/src/components/MatchListTable.tsx`
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Write failing apiClient tests**

Add to `web/src/apiClient.test.ts` imports:

```typescript
  saveZqcf918MatchId,
  syncFilteredZqcf918MatchIds,
  syncFilteredZqcf918Odds,
  syncSingleZqcf918Odds
```

Add tests:

```typescript
  it("syncs filtered zqcf918 match ids with serialized filters", async () => {
    const fetchMock = vi.fn(async () => Response.json({ report: { target_count: 0 } }));
    vi.stubGlobal("fetch", fetchMock);

    await syncFilteredZqcf918MatchIds({
      end_time: "2026-06-27T12:00:00+08:00",
      odds_filter: ["none", "partial"],
      start_time: "2026-06-26T00:00:00+08:00"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/match-list/sync/zqcf918-match-ids",
      expect.objectContaining({
        body: JSON.stringify({
          end_time: "2026-06-27T12:00:00+08:00",
          odds_filter: "none,partial",
          start_time: "2026-06-26T00:00:00+08:00"
        }),
        method: "POST"
      })
    );
  });

  it("syncs filtered zqcf918 odds with serialized filters", async () => {
    const fetchMock = vi.fn(async () => Response.json({ report: { target_count: 0 } }));
    vi.stubGlobal("fetch", fetchMock);

    await syncFilteredZqcf918Odds({
      end_time: "2026-06-27T12:00:00+08:00",
      odds_filter: ["none", "partial"],
      start_time: "2026-06-26T00:00:00+08:00"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/match-list/sync/zqcf918-odds",
      expect.objectContaining({
        body: JSON.stringify({
          end_time: "2026-06-27T12:00:00+08:00",
          odds_filter: "none,partial",
          start_time: "2026-06-26T00:00:00+08:00"
        }),
        method: "POST"
      })
    );
  });

  it("syncs single zqcf918 odds", async () => {
    const fetchMock = vi.fn(async () => Response.json({ report: { target_count: 1 } }));
    vi.stubGlobal("fetch", fetchMock);

    await syncSingleZqcf918Odds(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/matches/42/sync/zqcf918-odds",
      expect.objectContaining({ body: JSON.stringify({}), method: "POST" })
    );
  });

  it("saves zqcf918 match id", async () => {
    const fetchMock = vi.fn(async () => Response.json({ source_fixture_id: "4460916" }));
    vi.stubGlobal("fetch", fetchMock);

    await saveZqcf918MatchId(42, "4460916");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/matches/42/zqcf918-match-id",
      expect.objectContaining({
        body: JSON.stringify({ match_id: "4460916" }),
        method: "PUT"
      })
    );
  });
```

- [ ] **Step 2: Run apiClient tests to verify they fail**

Run:

```bash
npm --prefix web test -- apiClient.test.ts --runInBand
```

Expected: FAIL because functions do not exist. If Vitest rejects `--runInBand`, run `npm --prefix web test -- apiClient.test.ts`.

- [ ] **Step 3: Add frontend types and API functions**

Modify `web/src/types.ts`:

```typescript
export type Zqcf918MatchIdUpdateResult = {
  match_id: number;
  source_name: "zqcf918" | string;
  source_fixture_id: string;
  match_confidence: string;
  match_reason: string;
};

export type MatchDetail = MatchListMatch & {
  team_data_note: string;
  zqcf918_match_id: string | null;
  zqcf918_match_url: string | null;
  execution_timepoint_coverage: ExecutionTimepointCoverage;
  paper_recommendation_summary: RecommendationSummaryPlaceholder;
  formal_recommendation_summary: RecommendationSummaryPlaceholder;
};
```

Modify `web/src/apiClient.ts`:

```typescript
export async function syncFilteredZqcf918MatchIds(filters: {
  end_time?: string;
  league_name?: string | null;
  odds_filter?: string | string[];
  search?: string | null;
  start_time?: string;
  status_filter?: string;
}): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>("/api/match-list/sync/zqcf918-match-ids", {
    ...filters,
    odds_filter: serializeOddsFilter(filters.odds_filter)
  });
}

export async function syncFilteredZqcf918Odds(filters: {
  end_time?: string;
  league_name?: string | null;
  odds_filter?: string | string[];
  search?: string | null;
  start_time?: string;
  status_filter?: string;
}): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>("/api/match-list/sync/zqcf918-odds", {
    ...filters,
    odds_filter: serializeOddsFilter(filters.odds_filter)
  });
}

export async function syncSingleZqcf918Odds(matchId: number): Promise<MatchSyncResponse> {
  return await postJson<MatchSyncResponse>(`/api/matches/${matchId}/sync/zqcf918-odds`, {});
}

export async function saveZqcf918MatchId(
  matchId: number,
  zqcf918MatchId: string
): Promise<Zqcf918MatchIdUpdateResult> {
  return await putJson<Zqcf918MatchIdUpdateResult>(
    `/api/matches/${matchId}/zqcf918-match-id`,
    { match_id: zqcf918MatchId }
  );
}
```

If `putJson` does not exist, add it next to `postJson`:

```typescript
async function putJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "PUT"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 4: Add UI handlers and buttons**

In `web/src/components/MatchListTable.tsx`, extend props:

```typescript
  onSyncZqcf918Odds?: (match: MatchListMatch) => void;
```

Render a third row action with text `财富赔率`:

```tsx
                <button
                  disabled={isBusy}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSyncZqcf918Odds?.(row.match);
                  }}
                  type="button"
                >
                  财富赔率
                </button>
```

In the match-list action panel in `web/src/pages/DashboardPage.tsx`, add two batch buttons wired to props or local handlers:

```tsx
<button disabled={actionInFlight != null} onClick={onSyncZqcf918MatchIds} type="button">
  同步财富 matchID
</button>
<button disabled={actionInFlight != null} onClick={onSyncZqcf918Odds} type="button">
  同步财富赔率
</button>
```

In `web/src/pages/DashboardPage.tsx`, import:

```typescript
  saveZqcf918MatchId,
  syncFilteredZqcf918MatchIds,
  syncFilteredZqcf918Odds,
  syncSingleZqcf918Odds,
```

Add batch handlers near the existing odds sync handler:

```typescript
            onSyncZqcf918MatchIds={() => {
              const total = data.matchList.total_matches;
              if (total > 50 && !window.confirm(`当前筛选包含 ${total} 场比赛，确认同步足球财富 matchID？`)) {
                return;
              }
              setMatchListAction("sync-zqcf918-match-ids");
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncFilteredZqcf918MatchIds(matchListFilters)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("足球财富 matchID 同步完成"))
                .catch((error) => setMatchListError(formatActionError("足球财富 matchID 同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
            onSyncZqcf918Odds={() => {
              const total = data.matchList.total_matches;
              if (total > 50 && !window.confirm(`当前筛选包含 ${total} 场比赛，确认同步足球财富赔率？`)) {
                return;
              }
              setMatchListAction("sync-zqcf918-odds");
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncFilteredZqcf918Odds(matchListFilters)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("足球财富赔率同步完成"))
                .catch((error) => setMatchListError(formatActionError("足球财富赔率同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
```

Add single-match handler:

```typescript
            onSyncMatchZqcf918Odds={(match) => {
              setMatchListAction(`sync-zqcf918-odds-${match.match_id}`);
              setMatchListError(null);
              setMatchListMessage(null);
              setMatchListSyncReport(null);
              setMatchListSyncRunDetail(null);
              syncSingleZqcf918Odds(match.match_id)
                .then((response) => {
                  setMatchListSyncReport(response.report);
                  setMatchListSyncRunDetail(response);
                  return refreshMatchListWorkspace(setData, matchListFilters);
                })
                .then(() => setMatchListMessage("足球财富赔率同步完成"))
                .catch((error) => setMatchListError(formatActionError("足球财富赔率同步失败", error)))
                .finally(() => setMatchListAction(null));
            }}
```

Add `formatMatchListAction` branches:

```typescript
  if (action === "sync-zqcf918-match-ids") {
    return "同步足球财富 matchID";
  }
  if (action === "sync-zqcf918-odds") {
    return "同步足球财富赔率";
  }
```

Add a compact detail editor inside `MatchDetailView`:

```tsx
      <Panel title="足球财富">
        <Zqcf918MatchIdEditor
          detail={detail}
          onSaved={async () => onDetailUpdated(await loadMatchDetail(detail.match_id))}
        />
      </Panel>
```

Add component in the same file:

```tsx
function Zqcf918MatchIdEditor({
  detail,
  onSaved
}: {
  detail: MatchDetail;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(detail.zqcf918_match_id ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      await saveZqcf918MatchId(detail.match_id, draft);
      await onSaved();
      setMessage("足球财富 matchID 已保存");
    } catch (caught) {
      setError(formatActionError("保存足球财富 matchID 失败", caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="inline-form" onSubmit={submit}>
      <label>
        matchID
        <input value={draft} onChange={(event) => setDraft(event.target.value)} inputMode="numeric" />
      </label>
      <button disabled={isSaving || draft.trim() === ""} type="submit">
        保存
      </button>
      {detail.zqcf918_match_url && (
        <a href={detail.zqcf918_match_url} rel="noreferrer" target="_blank">
          打开
        </a>
      )}
      {message && <span className="inline-success">{message}</span>}
      {error && <span className="inline-warning">{error}</span>}
    </form>
  );
}
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
npm --prefix web test -- apiClient.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/types.ts web/src/apiClient.ts web/src/apiClient.test.ts web/src/components/MatchListTable.tsx web/src/pages/DashboardPage.tsx
git commit -m "feat: add zqcf918 web controls"
```
### Task 10: zqcf918 Comparison Diagnostic

**Files:**
- Create: `src/icewine_prediction/zqcf918_comparison_service.py`
- Create: `tests/test_zqcf918_comparison_service.py`

- [ ] **Step 1: Write failing comparison test**

Create `tests/test_zqcf918_comparison_service.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team
from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME, ZQCF918_SOURCE_NAME
from icewine_prediction.zqcf918_comparison_service import compare_zqcf918_to_trusted_source


def test_compare_zqcf918_to_trusted_source_reports_market_differences(session):
    match = _add_match(session)
    session.add_all(
        [
            _snapshot(match.id, THE_ODDS_API_SOURCE_NAME, "asian_handicap", "home", Decimal("-0.50"), Decimal("1.900")),
            _snapshot(match.id, THE_ODDS_API_SOURCE_NAME, "asian_handicap", "away", Decimal("-0.50"), Decimal("1.950")),
            _snapshot(match.id, ZQCF918_SOURCE_NAME, "asian_handicap", "home", Decimal("-0.50"), Decimal("1.910")),
            _snapshot(match.id, ZQCF918_SOURCE_NAME, "asian_handicap", "away", Decimal("-0.50"), Decimal("1.940")),
        ]
    )
    session.commit()

    report = compare_zqcf918_to_trusted_source(session, match_ids=[match.id])

    assert report.match_count == 1
    assert report.compared_group_count == 2
    assert report.rows[0].match_id == match.id
    assert report.rows[0].source_name == THE_ODDS_API_SOURCE_NAME
    assert report.rows[0].zqcf918_odds == Decimal("1.910")


def _add_match(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Home")
    away = Team(canonical_name="Away")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        status="finished",
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(match_id, source_name, market_type, side, line, odds):
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-{match_id}",
        bookmaker="pinnacle",
        market_type=market_type,
        market_id=f"{source_name}-{market_type}-{side}",
        market_name="Asian Handicap",
        market_line=line,
        outcome_side=side,
        odds=odds,
        snapshot_time=datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )
```

- [ ] **Step 2: Run comparison test to verify it fails**

Run:

```bash
pytest tests/test_zqcf918_comparison_service.py -q
```

Expected: FAIL because comparison service does not exist.

- [ ] **Step 3: Implement comparison service**

Create `src/icewine_prediction/zqcf918_comparison_service.py`:

```python
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)


@dataclass(frozen=True)
class ZQCF918ComparisonRow:
    match_id: int
    source_name: str
    market_type: str
    market_line: Decimal
    outcome_side: str
    snapshot_time: str
    trusted_odds: Decimal
    zqcf918_odds: Decimal
    absolute_diff: Decimal


@dataclass(frozen=True)
class ZQCF918ComparisonReport:
    match_count: int
    compared_group_count: int
    rows: list[ZQCF918ComparisonRow]


def compare_zqcf918_to_trusted_source(
    session: Session,
    *,
    match_ids: list[int],
    trusted_source_name: str = THE_ODDS_API_SOURCE_NAME,
) -> ZQCF918ComparisonReport:
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .filter(HistoricalOddsSnapshot.source_name.in_([trusted_source_name, ZQCF918_SOURCE_NAME]))
        .all()
    )
    by_key = {}
    for row in snapshots:
        key = (
            row.match_id,
            row.market_type,
            row.market_line,
            row.outcome_side,
            row.snapshot_time.isoformat(),
        )
        by_key.setdefault(key, {})[row.source_name] = row

    rows: list[ZQCF918ComparisonRow] = []
    for key, values in sorted(by_key.items()):
        trusted = values.get(trusted_source_name)
        zqcf918 = values.get(ZQCF918_SOURCE_NAME)
        if trusted is None or zqcf918 is None:
            continue
        rows.append(
            ZQCF918ComparisonRow(
                match_id=trusted.match_id,
                source_name=trusted.source_name,
                market_type=trusted.market_type,
                market_line=trusted.market_line,
                outcome_side=trusted.outcome_side,
                snapshot_time=trusted.snapshot_time.isoformat(),
                trusted_odds=trusted.odds,
                zqcf918_odds=zqcf918.odds,
                absolute_diff=abs(trusted.odds - zqcf918.odds),
            )
        )
    return ZQCF918ComparisonReport(
        match_count=len({row.match_id for row in rows}),
        compared_group_count=len(rows),
        rows=rows,
    )
```

- [ ] **Step 4: Run comparison tests**

Run:

```bash
pytest tests/test_zqcf918_comparison_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/zqcf918_comparison_service.py tests/test_zqcf918_comparison_service.py
git commit -m "feat: add zqcf918 odds comparison report"
```

---

### Task 11: Final Verification

**Files:**
- No new files unless verification exposes a defect.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
pytest tests/test_zqcf918_client.py tests/test_zqcf918_odds_mapper.py tests/test_zqcf918_match_service.py tests/test_zqcf918_sync_service.py tests/test_zqcf918_comparison_service.py tests/test_odds_provider_selection_service.py tests/test_match_odds_sync_service.py tests/test_web_console_api.py::test_web_console_api_updates_zqcf918_match_id_in_detail tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_match_ids tests/test_web_console_api.py::test_web_console_api_syncs_single_zqcf918_odds tests/test_web_console_api.py::test_web_console_api_syncs_filtered_zqcf918_odds -q
```

Expected: PASS.

- [ ] **Step 2: Run targeted frontend tests**

Run:

```bash
npm --prefix web test -- apiClient.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run formatting or type checks used by the project**

Run:

```bash
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only zqcf918 source, sync, API, frontend, and test files changed.

- [ ] **Step 5: Commit final fixes if any**

If Step 1, Step 2, or Step 3 required fixes, commit them:

```bash
git add <fixed-files>
git commit -m "fix: stabilize zqcf918 odds integration"
```

If no fixes were needed, do not create an empty commit.

---

## Scope Notes

- This plan does not perform real zqcf918 network calls in automated tests.
- The initial automatic match ID discovery uses the zqcf918 score-list endpoint observed in the current frontend bundle: `/new/website/real/time/getYPDX`. If implementation finds its fields differ by date or league, keep the manual match ID editor as the fallback and tighten discovery conservatively.
- The Web UI batch guard is frontend-only and applies to manual web actions over 50 currently filtered matches.
- The automatic fallback path does not require user confirmation and records per-match failures.



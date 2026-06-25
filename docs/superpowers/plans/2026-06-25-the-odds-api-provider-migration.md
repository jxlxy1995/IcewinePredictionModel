# The Odds API Provider Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace future Oddspapi Pinnacle ingestion with The Odds API while preserving old data and selecting Pinnacle snapshots by provider priority.

**Architecture:** Add a focused The Odds API provider path that maps API payloads into the existing `HistoricalOddsSnapshotInput` storage contract. Keep Oddspapi code as legacy, store new data under `source_name="the_odds_api"`, and add a shared Pinnacle snapshot selection helper with priority `the_odds_api` before `oddspapi`.

**Tech Stack:** Python 3.12, SQLAlchemy ORM, Typer CLI, pytest, existing `requests`-based API clients.

---

## File Structure

- Create `src/icewine_prediction/odds_provider_selection_service.py`
  - Own provider constants and source-priority filtering for Pinnacle historical snapshots.
- Create `src/icewine_prediction/sources/the_odds_api_odds_mapper.py`
  - Convert The Odds API `h2h`, `spreads`, and `totals` payloads into `HistoricalOddsSnapshotInput`.
- Create `src/icewine_prediction/the_odds_api_sync_runner.py`
  - Own sport-key mapping, event matching, candidate selection, fetch/store workflow, reports, and per-match status updates.
- Modify `src/icewine_prediction/sources/the_odds_api_client.py`
  - Add small endpoint convenience methods only if they keep runner code clearer.
- Modify `src/icewine_prediction/cli.py`
  - Wire `the-odds-api-plan`, `the-odds-api-fetch`, and `the-odds-api-match-report`.
- Modify `src/icewine_prediction/paper_recommendation_queue_service.py`
  - Use Pinnacle provider-priority snapshots instead of treating `oddspapi` as the only historical source.
- Modify `src/icewine_prediction/historical_training_sample_service.py`
  - Preserve explicit single-source behavior, and optionally allow priority reads through a new parameter without changing old default results.
- Test files:
  - Create `tests/test_the_odds_api_odds_mapper.py`
  - Create `tests/test_the_odds_api_sync_runner.py`
  - Create `tests/test_odds_provider_selection_service.py`
  - Modify `tests/test_oddspapi_sync_cli.py`
  - Modify `tests/test_paper_recommendation_queue_service.py`
  - Modify `tests/test_historical_training_sample_service.py`

## Task 1: Provider Constants And Priority Selection

**Files:**
- Create: `src/icewine_prediction/odds_provider_selection_service.py`
- Test: `tests/test_odds_provider_selection_service.py`

- [ ] **Step 1: Write failing tests for Pinnacle source-priority filtering**

Add `tests/test_odds_provider_selection_service.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    filter_priority_pinnacle_snapshots,
    source_label_for_snapshots,
)


def test_filter_priority_pinnacle_snapshots_prefers_the_odds_api_per_match():
    old = _snapshot(match_id=1, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))
    new = _snapshot(match_id=1, source_name=THE_ODDS_API_SOURCE_NAME, odds=Decimal("1.95"))
    ignored = _snapshot(match_id=1, source_name=THE_ODDS_API_SOURCE_NAME, bookmaker="bet365")

    selected = filter_priority_pinnacle_snapshots([old, new, ignored])

    assert selected == [new]
    assert source_label_for_snapshots(selected) == "the_odds_api_historical"


def test_filter_priority_pinnacle_snapshots_falls_back_to_oddspapi():
    old = _snapshot(match_id=2, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))

    selected = filter_priority_pinnacle_snapshots([old])

    assert selected == [old]
    assert source_label_for_snapshots(selected) == "oddspapi_historical"


def test_filter_priority_pinnacle_snapshots_keeps_each_match_independent():
    match_one_old = _snapshot(match_id=1, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90"))
    match_one_new = _snapshot(match_id=1, source_name=THE_ODDS_API_SOURCE_NAME, odds=Decimal("1.95"))
    match_two_old = _snapshot(match_id=2, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("2.05"))

    selected = filter_priority_pinnacle_snapshots([match_one_old, match_one_new, match_two_old])

    assert selected == [match_one_new, match_two_old]


def _snapshot(
    *,
    match_id: int,
    source_name: str,
    odds: Decimal,
    bookmaker: str = PINNACLE_BOOKMAKER,
) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-{match_id}",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"{source_name}-ah",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 6, 25, 12, 0, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_odds_provider_selection_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'icewine_prediction.odds_provider_selection_service'`.

- [ ] **Step 3: Implement provider selection helper**

Create `src/icewine_prediction/odds_provider_selection_service.py`:

```python
from collections import defaultdict
from typing import Iterable

from icewine_prediction.models import HistoricalOddsSnapshot


ODDSPAPI_SOURCE_NAME = "oddspapi"
THE_ODDS_API_SOURCE_NAME = "the_odds_api"
PINNACLE_BOOKMAKER = "pinnacle"
PINNACLE_SOURCE_PRIORITY = (THE_ODDS_API_SOURCE_NAME, ODDSPAPI_SOURCE_NAME)


def filter_priority_pinnacle_snapshots(
    snapshots: Iterable[HistoricalOddsSnapshot],
    *,
    source_priority: tuple[str, ...] = PINNACLE_SOURCE_PRIORITY,
    bookmaker: str = PINNACLE_BOOKMAKER,
) -> list[HistoricalOddsSnapshot]:
    grouped: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.bookmaker.lower() != bookmaker:
            continue
        if snapshot.source_name not in source_priority:
            continue
        grouped[snapshot.match_id].append(snapshot)

    selected: list[HistoricalOddsSnapshot] = []
    for match_id in sorted(grouped):
        match_snapshots = grouped[match_id]
        selected_source = _first_available_source(match_snapshots, source_priority)
        selected.extend(
            snapshot
            for snapshot in match_snapshots
            if snapshot.source_name == selected_source
        )
    return selected


def source_label_for_snapshots(snapshots: Iterable[HistoricalOddsSnapshot]) -> str:
    source_names = {snapshot.source_name for snapshot in snapshots}
    if THE_ODDS_API_SOURCE_NAME in source_names:
        return "the_odds_api_historical"
    if ODDSPAPI_SOURCE_NAME in source_names:
        return "oddspapi_historical"
    return "historical"


def _first_available_source(
    snapshots: list[HistoricalOddsSnapshot],
    source_priority: tuple[str, ...],
) -> str:
    available = {snapshot.source_name for snapshot in snapshots}
    for source_name in source_priority:
        if source_name in available:
            return source_name
    return snapshots[0].source_name
```

- [ ] **Step 4: Run tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_odds_provider_selection_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/odds_provider_selection_service.py tests/test_odds_provider_selection_service.py
git commit -m "feat: add pinnacle odds provider priority selection"
```

## Task 2: The Odds API Market Mapper

**Files:**
- Create: `src/icewine_prediction/sources/the_odds_api_odds_mapper.py`
- Test: `tests/test_the_odds_api_odds_mapper.py`

- [ ] **Step 1: Write failing mapper tests**

Add `tests/test_the_odds_api_odds_mapper.py`:

```python
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME
from icewine_prediction.sources.the_odds_api_odds_mapper import map_the_odds_api_event_odds


def test_map_the_odds_api_event_odds_maps_three_pinnacle_markets():
    event = {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": "2026-06-26T18:45:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": "2026-06-26T18:45:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": "Chelsea", "price": 3.40},
                        ],
                    },
                    {
                        "key": "spreads",
                        "last_update": "2026-06-26T18:46:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.91, "point": -0.25},
                            {"name": "Chelsea", "price": 1.99, "point": 0.25},
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": "2026-06-26T18:47:00Z",
                        "outcomes": [
                            {"name": "Over", "price": 1.88, "point": 2.5},
                            {"name": "Under", "price": 2.02, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }

    snapshots = map_the_odds_api_event_odds(match_id=42, event=event)

    assert len(snapshots) == 7
    assert {snapshot.source_name for snapshot in snapshots} == {THE_ODDS_API_SOURCE_NAME}
    assert {snapshot.bookmaker for snapshot in snapshots} == {"pinnacle"}
    assert {snapshot.market_type for snapshot in snapshots} == {
        "match_winner",
        "asian_handicap",
        "total_goals",
    }
    assert [snapshot.outcome_side for snapshot in snapshots if snapshot.market_type == "match_winner"] == [
        "home",
        "draw",
        "away",
    ]
    asian = [snapshot for snapshot in snapshots if snapshot.market_type == "asian_handicap"]
    assert {snapshot.outcome_side for snapshot in asian} == {"home", "away"}
    assert {snapshot.market_line for snapshot in asian} == {Decimal("-0.25")}
    totals = [snapshot for snapshot in snapshots if snapshot.market_type == "total_goals"]
    assert {snapshot.outcome_side for snapshot in totals} == {"over", "under"}
    assert {snapshot.market_line for snapshot in totals} == {Decimal("2.50")}
    assert {snapshot.snapshot_time for snapshot in snapshots} == {
        datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 6, 26, 18, 46, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 6, 26, 18, 47, tzinfo=ZoneInfo("UTC")),
    }


def test_map_the_odds_api_event_odds_ignores_non_pinnacle_bookmakers_and_incomplete_pairs():
    event = {
        "id": "event-2",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "bet365",
                "markets": [{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 2.10}]}],
            },
            {
                "key": "pinnacle",
                "last_update": "2026-06-26T18:45:00Z",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [{"name": "Arsenal", "price": 1.91, "point": -0.25}],
                    }
                ],
            },
        ],
    }

    assert map_the_odds_api_event_odds(match_id=42, event=event) == []
```

- [ ] **Step 2: Run mapper tests to verify they fail**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_the_odds_api_odds_mapper.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `the_odds_api_odds_mapper`.

- [ ] **Step 3: Implement mapper**

Create `src/icewine_prediction/sources/the_odds_api_odds_mapper.py`:

```python
from datetime import datetime
from decimal import Decimal
import json
from typing import Any
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import HistoricalOddsSnapshotInput
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
)


UTC = ZoneInfo("UTC")


def map_the_odds_api_event_odds(
    *,
    match_id: int,
    event: dict[str, Any],
    bookmaker: str = PINNACLE_BOOKMAKER,
) -> list[HistoricalOddsSnapshotInput]:
    bookmaker_payload = _find_bookmaker(event.get("bookmakers") or [], bookmaker)
    if bookmaker_payload is None:
        return []
    snapshots: list[HistoricalOddsSnapshotInput] = []
    for market in bookmaker_payload.get("markets") or []:
        market_key = str(market.get("key") or "")
        if market_key == "h2h":
            snapshots.extend(_map_h2h(match_id, event, market, bookmaker))
        elif market_key == "spreads":
            snapshots.extend(_map_spreads(match_id, event, market, bookmaker))
        elif market_key == "totals":
            snapshots.extend(_map_totals(match_id, event, market, bookmaker))
    return snapshots


def _map_h2h(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
) -> list[HistoricalOddsSnapshotInput]:
    home_team = str(event.get("home_team") or "")
    away_team = str(event.get("away_team") or "")
    sides = {}
    for outcome in market.get("outcomes") or []:
        name = str(outcome.get("name") or "")
        if name == home_team:
            sides["home"] = outcome
        elif name == away_team:
            sides["away"] = outcome
        elif name.lower() == "draw":
            sides["draw"] = outcome
    if not {"home", "draw", "away"}.issubset(sides):
        return []
    return [
        _snapshot(match_id, event, market, bookmaker, "match_winner", "Match Winner", Decimal("0.00"), side, sides[side])
        for side in ("home", "draw", "away")
    ]


def _map_spreads(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
) -> list[HistoricalOddsSnapshotInput]:
    home_team = str(event.get("home_team") or "")
    away_team = str(event.get("away_team") or "")
    by_side = {}
    for outcome in market.get("outcomes") or []:
        name = str(outcome.get("name") or "")
        if name == home_team:
            by_side["home"] = outcome
        elif name == away_team:
            by_side["away"] = outcome
    if not {"home", "away"}.issubset(by_side):
        return []
    home_line = _decimal(by_side["home"].get("point"))
    away_line = _decimal(by_side["away"].get("point"))
    if home_line is None or away_line is None or home_line != -away_line:
        return []
    return [
        _snapshot(match_id, event, market, bookmaker, "asian_handicap", "Asian Handicap", home_line, "home", by_side["home"]),
        _snapshot(match_id, event, market, bookmaker, "asian_handicap", "Asian Handicap", home_line, "away", by_side["away"]),
    ]


def _map_totals(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
) -> list[HistoricalOddsSnapshotInput]:
    by_side = {}
    for outcome in market.get("outcomes") or []:
        name = str(outcome.get("name") or "").lower()
        if name in {"over", "under"}:
            by_side[name] = outcome
    if not {"over", "under"}.issubset(by_side):
        return []
    line = _decimal(by_side["over"].get("point"))
    under_line = _decimal(by_side["under"].get("point"))
    if line is None or under_line is None or line != under_line:
        return []
    return [
        _snapshot(match_id, event, market, bookmaker, "total_goals", "Total Goals", line, "over", by_side["over"]),
        _snapshot(match_id, event, market, bookmaker, "total_goals", "Total Goals", line, "under", by_side["under"]),
    ]


def _snapshot(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
    market_type: str,
    market_name: str,
    market_line: Decimal,
    outcome_side: str,
    outcome: dict[str, Any],
) -> HistoricalOddsSnapshotInput:
    event_id = str(event.get("id") or "")
    market_key = str(market.get("key") or market_type)
    snapshot_time = _parse_time(market.get("last_update") or event.get("last_update") or event.get("commence_time"))
    return HistoricalOddsSnapshotInput(
        match_id=match_id,
        source_name=THE_ODDS_API_SOURCE_NAME,
        source_fixture_id=event_id,
        bookmaker=bookmaker,
        market_type=market_type,
        market_id=f"{event_id}:{market_key}:{market_line}:{outcome_side}",
        market_name=market_name,
        market_line=market_line,
        outcome_side=outcome_side,
        odds=_decimal(outcome.get("price")) or Decimal("0.00"),
        snapshot_time=snapshot_time,
        period="full_time",
        raw_payload=json.dumps({"event": event, "market": market, "outcome": outcome}, sort_keys=True),
    )


def _find_bookmaker(bookmakers: list[dict[str, Any]], bookmaker: str) -> dict[str, Any] | None:
    bookmaker = bookmaker.lower()
    for item in bookmakers:
        if str(item.get("key") or "").lower() == bookmaker:
            return item
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.00")) if "point" not in str(value) else Decimal(str(value))


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.now(tz=UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
```

Use this `_decimal` helper so prices and lines keep the provider value exactly:

```python
def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
```

The storage layer already controls numeric column precision; the tests assert Decimal equality, not string quantization.

- [ ] **Step 4: Run mapper tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_the_odds_api_odds_mapper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/sources/the_odds_api_odds_mapper.py tests/test_the_odds_api_odds_mapper.py
git commit -m "feat: map the odds api pinnacle markets"
```

## Task 3: The Odds API Sync Runner

**Files:**
- Create: `src/icewine_prediction/the_odds_api_sync_runner.py`
- Test: `tests/test_the_odds_api_sync_runner.py`

- [ ] **Step 1: Write failing tests for sport mapping, event matching, and fetch/store**

Add `tests/test_the_odds_api_sync_runner.py`:

```python
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME
from icewine_prediction.the_odds_api_sync_runner import (
    API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS,
    TheOddsApiSyncClient,
    build_the_odds_api_sync_plan_for_session,
    find_best_the_odds_api_event_match,
    run_the_odds_api_sync_for_session,
)


class FakeTheOddsApiClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.request_count = 0

    def get(self, endpoint, params=None):
        self.calls.append((endpoint, params or {}))
        self.request_count += 1
        return self.payloads[endpoint]


def test_sport_key_mapping_contains_mainstream_leagues():
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["140"] == "soccer_spain_la_liga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["78"] == "soccer_germany_bundesliga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["179"] == "soccer_spl"


def test_find_best_the_odds_api_event_match_uses_time_and_team_names(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    events = [
        {
            "id": "bad-time",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "commence_time": "2026-06-26T12:00:00Z",
        },
        {
            "id": "event-1",
            "home_team": "Arsenal FC",
            "away_team": "Chelsea",
            "commence_time": "2026-06-26T19:00:00Z",
        },
    ]

    candidate = find_best_the_odds_api_event_match(match, events)

    assert candidate is not None
    assert candidate.event_id == "event-1"
    assert candidate.confidence == Decimal("1.0000")


def test_run_the_odds_api_sync_stores_snapshots_under_distinct_source(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "sports/soccer_epl/odds": [
                    {
                        "id": "event-1",
                        "home_team": "Arsenal",
                        "away_team": "Chelsea",
                        "commence_time": "2026-06-26T19:00:00Z",
                        "bookmakers": [
                            {
                                "key": "pinnacle",
                                "last_update": "2026-06-26T18:45:00Z",
                                "markets": [
                                    {
                                        "key": "h2h",
                                        "outcomes": [
                                            {"name": "Arsenal", "price": 2.10},
                                            {"name": "Draw", "price": 3.30},
                                            {"name": "Chelsea", "price": 3.40},
                                        ],
                                    },
                                    {
                                        "key": "spreads",
                                        "outcomes": [
                                            {"name": "Arsenal", "price": 1.91, "point": -0.25},
                                            {"name": "Chelsea", "price": 1.99, "point": 0.25},
                                        ],
                                    },
                                    {
                                        "key": "totals",
                                        "outcomes": [
                                            {"name": "Over", "price": 1.88, "point": 2.5},
                                            {"name": "Under", "price": 2.02, "point": 2.5},
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
    )

    assert result.processed_match_count == 1
    assert result.matched_count == 1
    assert result.inserted_snapshot_count == 7
    snapshots = session.query(HistoricalOddsSnapshot).all()
    assert {snapshot.source_name for snapshot in snapshots} == {THE_ODDS_API_SOURCE_NAME}
    assert {snapshot.bookmaker for snapshot in snapshots} == {"pinnacle"}
    status = session.query(OddsSourceMatch).one()
    assert status.source_name == THE_ODDS_API_SOURCE_NAME
    assert status.source_fixture_id == "event-1"
    assert status.historical_odds_status == "success"


def test_build_the_odds_api_sync_plan_skips_matches_with_existing_source_snapshots(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name=THE_ODDS_API_SOURCE_NAME,
            source_fixture_id="event-1",
            bookmaker="pinnacle",
            market_type="asian_handicap",
            market_id="event-1:spreads:-0.25:home",
            market_name="Asian Handicap",
            market_line=Decimal("-0.25"),
            outcome_side="home",
            odds=Decimal("1.91"),
            snapshot_time=datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
            period="full_time",
        )
    )
    session.commit()

    plan = build_the_odds_api_sync_plan_for_session(session=session, season=2026, max_matches=5)

    assert plan.candidate_match_count == 0
    assert plan.skipped_existing_odds_count == 1


def _add_match(
    session,
    *,
    home_team_name: str,
    away_team_name: str,
    source_league_id: str = "39",
) -> Match:
    league = League(
        name="Premier League",
        country_or_region="England",
        level=1,
        is_enabled=True,
        source_name="api_football",
        source_league_id=source_league_id,
    )
    home = Team(canonical_name=home_team_name)
    away = Team(canonical_name=away_team_name)
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.commit()
    return match
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_the_odds_api_sync_runner.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'icewine_prediction.the_odds_api_sync_runner'`.

- [ ] **Step 3: Implement runner dataclasses and mapping**

Create `src/icewine_prediction/the_odds_api_sync_runner.py` with these public constants and dataclasses:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.historical_odds_service import store_historical_odds_snapshots
from icewine_prediction.models import HistoricalOddsSnapshot, Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
)
from icewine_prediction.odds_source_match_service import normalize_team_name
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.the_odds_api_client import (
    TheOddsApiApiError,
    TheOddsApiClient,
    TheOddsApiRequestBudgetExceededError,
)
from icewine_prediction.sources.the_odds_api_odds_mapper import map_the_odds_api_event_odds
from icewine_prediction.time_utils import now_beijing


UTC = ZoneInfo("UTC")
DEFAULT_REGION = "eu"
DEFAULT_MARKETS = ("h2h", "spreads", "totals")
API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS = {
    "1": "soccer_fifa_world_cup",
    "39": "soccer_epl",
    "40": "soccer_efl_champ",
    "61": "soccer_france_ligue_one",
    "62": "soccer_france_ligue_two",
    "71": "soccer_brazil_campeonato",
    "78": "soccer_germany_bundesliga",
    "79": "soccer_germany_bundesliga2",
    "88": "soccer_netherlands_eredivisie",
    "94": "soccer_portugal_primeira_liga",
    "98": "soccer_japan_j_league",
    "135": "soccer_italy_serie_a",
    "136": "soccer_italy_serie_b",
    "140": "soccer_spain_la_liga",
    "179": "soccer_spl",
    "188": "soccer_australia_aleague",
    "253": "soccer_usa_mls",
    "262": "soccer_mexico_ligamx",
    "292": "soccer_korea_kleague1",
}


@dataclass(frozen=True)
class TheOddsApiPlanMatch:
    match_id: int
    league_name: str
    sport_key: str
    kickoff_time: datetime
    home_team_name: str
    away_team_name: str
    estimated_request_count: int


@dataclass(frozen=True)
class TheOddsApiSyncPlan:
    candidate_match_count: int
    estimated_request_count: int
    skipped_existing_odds_count: int
    candidate_matches: tuple[TheOddsApiPlanMatch, ...] = ()


@dataclass(frozen=True)
class TheOddsApiEventMatchCandidate:
    event_id: str
    event: dict[str, Any]
    confidence: Decimal
    reason: str


@dataclass(frozen=True)
class TheOddsApiSyncResult:
    processed_match_count: int
    matched_count: int
    failed_match_count: int
    inserted_snapshot_count: int
    skipped_duplicate_snapshot_count: int
    skipped_existing_odds_count: int
    asian_handicap_count: int
    total_goals_count: int
    match_winner_count: int
    requests_used: int
    error_message: str | None = None
```

- [ ] **Step 4: Implement client wrapper, candidate selection, and event matching**

Append these functions/classes:

```python
class TheOddsApiSyncClient:
    def __init__(
        self,
        client: Any,
        *,
        bookmaker: str = PINNACLE_BOOKMAKER,
        region: str = DEFAULT_REGION,
        markets: tuple[str, ...] = DEFAULT_MARKETS,
    ) -> None:
        self.client = client
        self.bookmaker = bookmaker
        self.region = region
        self.markets = markets

    @property
    def request_count(self) -> int:
        return getattr(self.client, "request_count", 0)

    def fetch_current_odds(self, sport_key: str) -> list[dict[str, Any]]:
        payload = self.client.get(
            f"sports/{sport_key}/odds",
            {
                "regions": self.region,
                "bookmakers": self.bookmaker,
                "markets": ",".join(self.markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        return list(payload if isinstance(payload, list) else [])


def find_best_the_odds_api_event_match(
    match: Match,
    events: list[dict[str, Any]],
    *,
    max_time_delta_seconds: int = 7200,
) -> TheOddsApiEventMatchCandidate | None:
    candidates = []
    kickoff = _as_utc(match.kickoff_time)
    for event in events:
        commence_time = _parse_time(event.get("commence_time"))
        if commence_time is None:
            continue
        time_delta = abs((kickoff - commence_time).total_seconds())
        if time_delta > max_time_delta_seconds:
            continue
        home_score = _team_similarity(match.home_team.canonical_name, str(event.get("home_team") or ""))
        away_score = _team_similarity(match.away_team.canonical_name, str(event.get("away_team") or ""))
        if home_score == Decimal("0") or away_score == Decimal("0"):
            continue
        candidates.append(
            TheOddsApiEventMatchCandidate(
                event_id=str(event.get("id") or ""),
                event=event,
                confidence=min(home_score, away_score),
                reason=f"sport/time/team match; time_delta_seconds={int(time_delta)}",
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)


def select_the_odds_api_candidate_matches(
    session: Session,
    *,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
) -> tuple[list[Match], int]:
    query = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.season == season)
        .filter(Match.status.in_(("scheduled", "finished")))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
    )
    if league_ids:
        query = query.filter(Match.league.has(source_league_id=None) | Match.league.has(source_league_id.in_(league_ids)))
    if match_ids:
        query = query.filter(Match.id.in_(match_ids))
    if from_date is not None:
        query = query.filter(Match.kickoff_time >= from_date)

    matches = []
    skipped = 0
    for match in query.all():
        if str(match.league.source_league_id) not in API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS:
            continue
        if not refresh_existing and _has_existing_snapshots(session, match.id):
            skipped += 1
            continue
        matches.append(match)
        if len(matches) >= max_matches:
            break
    return matches, skipped
```

When implementing the `league_ids` filter, use a direct join if the `has(...in_)` expression is awkward:

```python
from icewine_prediction.models import League

query = query.join(League, Match.league_id == League.id)
if league_ids:
    query = query.filter(League.source_league_id.in_(league_ids))
```

- [ ] **Step 5: Implement plan, run, status, and format helpers**

Append:

```python
def build_the_odds_api_sync_plan_for_session(
    *,
    session: Session,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
) -> TheOddsApiSyncPlan:
    matches, skipped = select_the_odds_api_candidate_matches(
        session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        match_ids=match_ids,
        from_date=from_date,
    )
    plan_matches = tuple(
        TheOddsApiPlanMatch(
            match_id=match.id,
            league_name=match.league.name,
            sport_key=API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS[str(match.league.source_league_id)],
            kickoff_time=match.kickoff_time,
            home_team_name=match.home_team.canonical_name,
            away_team_name=match.away_team.canonical_name,
            estimated_request_count=1,
        )
        for match in matches
    )
    return TheOddsApiSyncPlan(
        candidate_match_count=len(plan_matches),
        estimated_request_count=len({item.sport_key for item in plan_matches}),
        skipped_existing_odds_count=skipped,
        candidate_matches=plan_matches,
    )


def run_the_odds_api_sync_for_session(
    *,
    session: Session,
    client: TheOddsApiSyncClient,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
) -> TheOddsApiSyncResult:
    matches, skipped = select_the_odds_api_candidate_matches(
        session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        match_ids=match_ids,
        from_date=from_date,
        refresh_existing=refresh_existing,
    )
    events_by_sport_key: dict[str, list[dict[str, Any]]] = {}
    processed = matched = failed = inserted = skipped_duplicates = 0
    asian = totals = winners = 0
    for match in matches:
        sport_key = API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS[str(match.league.source_league_id)]
        try:
            if sport_key not in events_by_sport_key:
                events_by_sport_key[sport_key] = client.fetch_current_odds(sport_key)
            candidate = find_best_the_odds_api_event_match(match, events_by_sport_key[sport_key])
            if candidate is None:
                _store_source_match_status(session, match, None, "unmatched", "no matching The Odds API event")
                failed += 1
                continue
            snapshots = map_the_odds_api_event_odds(match_id=match.id, event=candidate.event)
            if not snapshots:
                _store_source_match_status(session, match, candidate, "empty", "no Pinnacle markets")
                failed += 1
                continue
            result = store_historical_odds_snapshots(
                session,
                snapshots,
                max_snapshots_per_match=400,
                kickoff_time=match.kickoff_time,
                execution_timepoint_source_snapshots=snapshots,
            )
            _store_source_match_status(session, match, candidate, "success", None)
            matched += 1
            processed += 1
            inserted += result.inserted_count
            skipped_duplicates += result.skipped_duplicate_count
            asian += sum(1 for snapshot in snapshots if snapshot.market_type == "asian_handicap")
            totals += sum(1 for snapshot in snapshots if snapshot.market_type == "total_goals")
            winners += sum(1 for snapshot in snapshots if snapshot.market_type == "match_winner")
        except (TheOddsApiApiError, TheOddsApiRequestBudgetExceededError) as exc:
            _store_source_match_status(session, match, None, "failed", str(exc))
            failed += 1
            break
    return TheOddsApiSyncResult(
        processed_match_count=processed,
        matched_count=matched,
        failed_match_count=failed,
        inserted_snapshot_count=inserted,
        skipped_duplicate_snapshot_count=skipped_duplicates,
        skipped_existing_odds_count=skipped,
        asian_handicap_count=asian,
        total_goals_count=totals,
        match_winner_count=winners,
        requests_used=client.request_count,
    )
```

- [ ] **Step 6: Implement runner helper functions and public wrappers**

Append these helper functions in `src/icewine_prediction/the_odds_api_sync_runner.py`:

```python
def build_the_odds_api_sync_plan(
    *,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
) -> str:
    with _open_session() as session:
        plan = build_the_odds_api_sync_plan_for_session(
            session=session,
            season=season,
            max_matches=max_matches,
            league_ids=league_ids,
            match_ids=match_ids,
            from_date=from_date,
        )
    return format_the_odds_api_sync_plan(plan)


def run_the_odds_api_sync(
    *,
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
    bookmaker: str = PINNACLE_BOOKMAKER,
    region: str = DEFAULT_REGION,
) -> str:
    settings = load_project_settings()
    raw_client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = TheOddsApiSyncClient(raw_client, bookmaker=bookmaker, region=region)
    with _open_session() as session:
        result = run_the_odds_api_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            league_ids=league_ids,
            match_ids=match_ids,
            from_date=from_date,
            refresh_existing=refresh_existing,
        )
    return format_the_odds_api_sync_result(result)


def build_the_odds_api_match_report(match_id: int) -> str:
    with _open_session() as session:
        match = session.query(Match).filter(Match.id == match_id).one_or_none()
        if match is None:
            return f"match not found id={match_id}"
        snapshots = (
            session.query(HistoricalOddsSnapshot)
            .filter(HistoricalOddsSnapshot.match_id == match_id)
            .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
            .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
            .order_by(
                HistoricalOddsSnapshot.market_type,
                HistoricalOddsSnapshot.snapshot_time,
                HistoricalOddsSnapshot.market_line,
                HistoricalOddsSnapshot.outcome_side,
            )
            .all()
        )
        lines = [
            f"{match.id} {match.home_team.canonical_name} vs {match.away_team.canonical_name}",
            f"the_odds_api pinnacle snapshots={len(snapshots)}",
        ]
        for snapshot in snapshots:
            lines.append(
                f"{snapshot.snapshot_time.isoformat()} {snapshot.market_type} "
                f"line={snapshot.market_line} {snapshot.outcome_side} odds={snapshot.odds}"
            )
        return "\n".join(lines)


def format_the_odds_api_sync_plan(plan: TheOddsApiSyncPlan) -> str:
    lines = [
        "The Odds API Sync Plan",
        f"candidate_matches={plan.candidate_match_count}",
        f"estimated_requests={plan.estimated_request_count}",
        f"skipped_existing_odds={plan.skipped_existing_odds_count}",
    ]
    for item in plan.candidate_matches:
        lines.append(
            f"- match_id={item.match_id} sport={item.sport_key} "
            f"{item.home_team_name} vs {item.away_team_name} kickoff={item.kickoff_time.isoformat()}"
        )
    return "\n".join(lines)


def format_the_odds_api_sync_result(result: TheOddsApiSyncResult) -> str:
    return "\n".join(
        [
            "The Odds API Sync Result",
            f"processed={result.processed_match_count}",
            f"matched={result.matched_count}",
            f"failed={result.failed_match_count}",
            f"inserted_snapshots={result.inserted_snapshot_count}",
            f"skipped_duplicates={result.skipped_duplicate_snapshot_count}",
            f"skipped_existing_odds={result.skipped_existing_odds_count}",
            f"asian_handicap={result.asian_handicap_count}",
            f"total_goals={result.total_goals_count}",
            f"match_winner={result.match_winner_count}",
            f"requests_used={result.requests_used}",
        ]
    )


def _has_existing_snapshots(session: Session, match_id: int) -> bool:
    return (
        session.query(HistoricalOddsSnapshot.id)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .first()
        is not None
    )


def _store_source_match_status(
    session: Session,
    match: Match,
    candidate: TheOddsApiEventMatchCandidate | None,
    status: str,
    error: str | None,
) -> None:
    row = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.match_id == match.id)
        .filter(OddsSourceMatch.source_name == THE_ODDS_API_SOURCE_NAME)
        .one_or_none()
    )
    if row is None:
        row = OddsSourceMatch(
            match_id=match.id,
            source_name=THE_ODDS_API_SOURCE_NAME,
            source_fixture_id=candidate.event_id if candidate is not None else f"unmatched-{match.id}",
            matched_at=now_beijing(),
            match_confidence=candidate.confidence if candidate is not None else Decimal("0.0000"),
            match_reason=candidate.reason if candidate is not None else status,
        )
        session.add(row)
    elif candidate is not None:
        row.source_fixture_id = candidate.event_id
        row.match_confidence = candidate.confidence
        row.match_reason = candidate.reason
    row.historical_odds_status = status
    row.historical_odds_checked_at = now_beijing()
    row.historical_odds_error = error
    session.commit()


def _team_similarity(left: str, right: str) -> Decimal:
    normalized_left = normalize_team_name(left)
    normalized_right = normalize_team_name(right)
    if normalized_left == normalized_right:
        return Decimal("1.0000")
    if normalized_left and normalized_right and (
        normalized_left in normalized_right or normalized_right in normalized_left
    ):
        return Decimal("0.9000")
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    if not left_tokens or not right_tokens:
        return Decimal("0")
    overlap = left_tokens & right_tokens
    if not overlap:
        return Decimal("0")
    return Decimal(len(overlap)) / Decimal(max(len(left_tokens), len(right_tokens)))


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return value.astimezone(UTC)
```

Add `_open_session` at the bottom of the module:

```python
def _open_session():
    from icewine_prediction.database import (
        create_database_engine,
        create_session_factory,
        initialize_database,
    )

    engine = create_database_engine()
    initialize_database(engine)
    return create_session_factory(engine)()
```

- [ ] **Step 7: Run sync runner tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_the_odds_api_sync_runner.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/icewine_prediction/the_odds_api_sync_runner.py tests/test_the_odds_api_sync_runner.py
git commit -m "feat: add the odds api sync runner"
```

## Task 4: CLI Wiring

**Files:**
- Modify: `src/icewine_prediction/cli.py`
- Modify: `tests/test_oddspapi_sync_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/test_oddspapi_sync_cli.py`:

```python
def test_the_odds_api_plan_accepts_filters(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_the_odds_api_sync_plan",
        lambda season, max_matches, league_ids, match_ids, from_date: (
            f"plan:{season}:{max_matches}:{sorted(league_ids or [])}:{sorted(match_ids or [])}:{from_date}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "the-odds-api-plan",
            "--season",
            "2026",
            "--max-matches",
            "3",
            "--league-ids",
            "39,140",
            "--match-ids",
            "10,11",
        ],
    )

    assert result.exit_code == 0
    assert "plan:2026:3:['140', '39']:[10, 11]" in result.stdout


def test_the_odds_api_fetch_accepts_runtime_options(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.run_the_odds_api_sync",
        lambda season, max_matches, request_budget, timeout_seconds, league_ids, match_ids, from_date, refresh_existing, bookmaker, region: (
            f"fetch:{season}:{max_matches}:{request_budget}:{timeout_seconds}:"
            f"{sorted(league_ids or [])}:{sorted(match_ids or [])}:{refresh_existing}:{bookmaker}:{region}"
        ),
    )

    result = runner.invoke(
        app,
        [
            "odds-source",
            "the-odds-api-fetch",
            "--season",
            "2026",
            "--max-matches",
            "2",
            "--request-budget",
            "5",
            "--timeout-seconds",
            "12",
            "--league-ids",
            "39",
            "--match-ids",
            "10",
            "--refresh-existing",
        ],
    )

    assert result.exit_code == 0
    assert "fetch:2026:2:5:12:['39']:[10]:True:pinnacle:eu" in result.stdout


def test_the_odds_api_match_report_accepts_match_id(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.build_the_odds_api_match_report",
        lambda match_id: f"match-report:{match_id}",
    )

    result = runner.invoke(app, ["odds-source", "the-odds-api-match-report", "--match-id", "42"])

    assert result.exit_code == 0
    assert "match-report:42" in result.stdout
```

Update `test_odds_source_group_exposes_oddspapi_commands` to assert:

```python
assert "the-odds-api-plan" in result.stdout
assert "the-odds-api-fetch" in result.stdout
assert "the-odds-api-match-report" in result.stdout
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_oddspapi_sync_cli.py -q
```

Expected: FAIL because commands/imports are missing.

- [ ] **Step 3: Wire CLI imports and commands**

In `src/icewine_prediction/cli.py`, extend existing The Odds API imports:

```python
from icewine_prediction.the_odds_api_sync_runner import (
    build_the_odds_api_match_report,
    build_the_odds_api_sync_plan,
    run_the_odds_api_sync,
)
```

Add commands near existing The Odds API probe commands:

```python
@odds_source_app.command("the-odds-api-plan")
def odds_source_the_odds_api_plan(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(10, "--max-matches"),
    league_ids: str = typer.Option("", "--league-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    from_date: datetime | None = typer.Option(None, "--from-date"),
):
    typer.echo(
        build_the_odds_api_sync_plan(
            season=season,
            max_matches=max_matches,
            league_ids=_parse_str_set(league_ids) or None,
            match_ids=_parse_id_set(match_ids) or None,
            from_date=from_date,
        )
    )


@odds_source_app.command("the-odds-api-fetch")
def odds_source_the_odds_api_fetch(
    season: int = typer.Option(..., "--season"),
    max_matches: int = typer.Option(10, "--max-matches"),
    request_budget: int = typer.Option(20, "--request-budget"),
    timeout_seconds: int = typer.Option(20, "--timeout-seconds"),
    league_ids: str = typer.Option("", "--league-ids"),
    match_ids: str = typer.Option("", "--match-ids"),
    from_date: datetime | None = typer.Option(None, "--from-date"),
    refresh_existing: bool = typer.Option(False, "--refresh-existing"),
    bookmaker: str = typer.Option("pinnacle", "--bookmaker"),
    region: str = typer.Option("eu", "--region"),
):
    typer.echo(
        run_the_odds_api_sync(
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            timeout_seconds=timeout_seconds,
            league_ids=_parse_str_set(league_ids) or None,
            match_ids=_parse_id_set(match_ids) or None,
            from_date=from_date,
            refresh_existing=refresh_existing,
            bookmaker=bookmaker,
            region=region,
        )
    )


@odds_source_app.command("the-odds-api-match-report")
def odds_source_the_odds_api_match_report(match_id: int = typer.Option(..., "--match-id")):
    typer.echo(build_the_odds_api_match_report(match_id=match_id))
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_oddspapi_sync_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/cli.py tests/test_oddspapi_sync_cli.py
git commit -m "feat: expose the odds api sync commands"
```

## Task 5: Source-Priority Reads In Paper Queue

**Files:**
- Modify: `src/icewine_prediction/paper_recommendation_queue_service.py`
- Modify: `tests/test_paper_recommendation_queue_service.py`

- [ ] **Step 1: Add failing paper queue test**

Append to `tests/test_paper_recommendation_queue_service.py`:

```python
def test_paper_queue_prefers_the_odds_api_pinnacle_snapshots_over_oddspapi(session):
    league = League(name="Premier League", country_or_region="England", level=1, is_enabled=True)
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        season=2026,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.flush()
    _add_historical_pair(session, match.id, "oddspapi", kickoff - timedelta(minutes=10), Decimal("-0.25"), Decimal("1.90"), Decimal("2.00"))
    _add_historical_pair(session, match.id, "the_odds_api", kickoff - timedelta(minutes=10), Decimal("-0.50"), Decimal("1.80"), Decimal("2.10"))
    session.commit()

    seen_rows = []

    def scorer(row):
        seen_rows.append(row)
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.4762"),
            edge=Decimal("0.1738"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        hours=12,
        scorer=scorer,
    )

    candidate = next(row for row in report.rows if row.status == "candidate")
    assert candidate.odds_source == "the_odds_api_historical"
    assert candidate.line == Decimal("-0.50")
    assert seen_rows[0]["asian_handicap_close_line"] == "-0.50"


def _add_historical_pair(session, match_id, source_name, snapshot_time, line, home_odds, away_odds):
    session.add_all(
        [
            HistoricalOddsSnapshot(
                match_id=match_id,
                source_name=source_name,
                source_fixture_id=f"{source_name}-event",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id=f"{source_name}:ah:home",
                market_name="Asian Handicap",
                market_line=line,
                outcome_side="home",
                odds=home_odds,
                snapshot_time=snapshot_time,
                period="full_time",
            ),
            HistoricalOddsSnapshot(
                match_id=match_id,
                source_name=source_name,
                source_fixture_id=f"{source_name}-event",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id=f"{source_name}:ah:away",
                market_name="Asian Handicap",
                market_line=line,
                outcome_side="away",
                odds=away_odds,
                snapshot_time=snapshot_time,
                period="full_time",
            ),
        ]
    )
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_paper_recommendation_queue_service.py::test_paper_queue_prefers_the_odds_api_pinnacle_snapshots_over_oddspapi -q
```

Expected: FAIL because paper queue labels historical data as `oddspapi_historical` and does not filter by source priority.

- [ ] **Step 3: Apply source-priority helper in paper queue**

In `src/icewine_prediction/paper_recommendation_queue_service.py`:

1. Replace the `ODDSPAPI_SOURCE_NAME` import usage for read selection with:

```python
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    filter_priority_pinnacle_snapshots,
    source_label_for_snapshots,
)
```

2. Change `_historical_snapshots_by_match_id` so it filters before grouping:

```python
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .all()
    )
    snapshots = filter_priority_pinnacle_snapshots(snapshots)
```

3. Change `_build_queue_rows_with_diagnostics`:

```python
    odds_source = source_label_for_snapshots(historical_snapshots) if historical_snapshots else "live_snapshot"
```

4. Change `_has_complete_historical_odds` relevant filter to remove the hard source check:

```python
    relevant = [
        snapshot
        for snapshot in snapshots
        if snapshot.bookmaker == "pinnacle"
        and kickoff_utc - timedelta(hours=24)
        <= _historical_snapshot_as_utc(snapshot.snapshot_time)
        <= kickoff_utc
    ]
```

- [ ] **Step 4: Run focused paper tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_paper_recommendation_queue_service.py::test_paper_queue_prefers_the_odds_api_pinnacle_snapshots_over_oddspapi -q
```

Expected: PASS.

- [ ] **Step 5: Run full paper queue tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_paper_recommendation_queue_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/icewine_prediction/paper_recommendation_queue_service.py tests/test_paper_recommendation_queue_service.py
git commit -m "feat: use pinnacle provider priority in paper queue"
```

## Task 6: Optional Priority Reads For Historical Training Samples

**Files:**
- Modify: `src/icewine_prediction/historical_training_sample_service.py`
- Modify: `tests/test_historical_training_sample_service.py`

- [ ] **Step 1: Add failing tests while preserving old default**

Append to `tests/test_historical_training_sample_service.py`:

```python
def test_historical_training_samples_default_remains_explicit_oddspapi(session):
    match = _add_finished_match(session)
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.25"),
        snapshot_time=match.kickoff_time - timedelta(hours=1),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.90"),
        side_b_odds=Decimal("1.96"),
        market_id="oddspapi-ah",
        source_name="oddspapi",
    )
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.50"),
        snapshot_time=match.kickoff_time - timedelta(hours=1),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.80"),
        side_b_odds=Decimal("2.10"),
        market_id="toa-ah",
        source_name="the_odds_api",
    )
    session.commit()

    samples = list_historical_market_training_samples(session, season=2026)

    assert samples[0].anchors[-1].market_line == Decimal("-0.25")


def test_historical_training_samples_can_use_pinnacle_provider_priority(session):
    match = _add_finished_match(session)
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.25"),
        snapshot_time=match.kickoff_time - timedelta(hours=1),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.90"),
        side_b_odds=Decimal("1.96"),
        market_id="oddspapi-ah",
        source_name="oddspapi",
    )
    _add_pair(
        session,
        match,
        market_type="asian_handicap",
        market_line=Decimal("-0.50"),
        snapshot_time=match.kickoff_time - timedelta(hours=1),
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.80"),
        side_b_odds=Decimal("2.10"),
        market_id="toa-ah",
        source_name="the_odds_api",
    )
    session.commit()

    samples = list_historical_market_training_samples(
        session,
        season=2026,
        source_name=None,
        use_pinnacle_provider_priority=True,
    )

    assert samples[0].anchors[-1].market_line == Decimal("-0.50")
```

If `_add_pair` in this file does not accept `source_name`, extend its signature:

```python
def _add_pair(..., source_name: str = "oddspapi"):
```

and pass `source_name=source_name` into each `HistoricalOddsSnapshot`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_historical_training_sample_service.py::test_historical_training_samples_can_use_pinnacle_provider_priority -q
```

Expected: FAIL because `use_pinnacle_provider_priority` is not accepted.

- [ ] **Step 3: Implement optional priority mode**

In `src/icewine_prediction/historical_training_sample_service.py`:

1. Import:

```python
from icewine_prediction.odds_provider_selection_service import filter_priority_pinnacle_snapshots
```

2. Change signature:

```python
def list_historical_market_training_samples(
    session: Session,
    *,
    season: int | None = None,
    limit: int | None = None,
    source_name: str | None = "oddspapi",
    bookmaker: str = "pinnacle",
    use_pinnacle_provider_priority: bool = False,
) -> list[HistoricalMarketTrainingSample]:
```

3. Pass `use_pinnacle_provider_priority` into `_load_historical_snapshots`.

4. Change `_load_historical_snapshots` signature and query:

```python
def _load_historical_snapshots(
    session: Session,
    *,
    match_ids: list[int],
    source_name: str | None,
    bookmaker: str,
    use_pinnacle_provider_priority: bool = False,
) -> dict[int, list[HistoricalOddsSnapshot]]:
    if not match_ids:
        return {}
    query = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.bookmaker == bookmaker)
    )
    if source_name is not None:
        query = query.filter(HistoricalOddsSnapshot.source_name == source_name)
    snapshots = query.order_by(HistoricalOddsSnapshot.snapshot_time.asc()).all()
    if use_pinnacle_provider_priority:
        snapshots = filter_priority_pinnacle_snapshots(snapshots, bookmaker=bookmaker)
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        snapshots_by_match_id[snapshot.match_id].append(snapshot)
    return snapshots_by_match_id
```

- [ ] **Step 4: Run historical training tests**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_historical_training_sample_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/icewine_prediction/historical_training_sample_service.py tests/test_historical_training_sample_service.py
git commit -m "feat: support pinnacle provider priority in training samples"
```

## Task 7: Final Verification And Small Live Dry Run

**Files:**
- No source changes unless verification exposes a bug.

- [ ] **Step 1: Run targeted unit suite**

Run:

```bash
C:\Python312\python.exe -m pytest tests/test_the_odds_api_client.py tests/test_the_odds_api_probe_service.py tests/test_the_odds_api_odds_mapper.py tests/test_the_odds_api_sync_runner.py tests/test_odds_provider_selection_service.py tests/test_oddspapi_sync_cli.py tests/test_paper_recommendation_queue_service.py tests/test_historical_training_sample_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
C:\Python312\python.exe -m ruff check src/icewine_prediction/odds_provider_selection_service.py src/icewine_prediction/sources/the_odds_api_odds_mapper.py src/icewine_prediction/the_odds_api_sync_runner.py src/icewine_prediction/cli.py src/icewine_prediction/paper_recommendation_queue_service.py src/icewine_prediction/historical_training_sample_service.py tests/test_the_odds_api_odds_mapper.py tests/test_the_odds_api_sync_runner.py tests/test_odds_provider_selection_service.py tests/test_oddspapi_sync_cli.py tests/test_paper_recommendation_queue_service.py tests/test_historical_training_sample_service.py
```

Expected: PASS.

- [ ] **Step 3: Run a no-write plan command**

Run:

```bash
C:\Python312\python.exe -m icewine_cli odds-source the-odds-api-plan --season 2026 --max-matches 3
```

Expected: Text report listing up to 3 candidate matches, estimated requests, and skipped existing The Odds API odds. This command must not write database rows.

- [ ] **Step 4: Run a tiny write test only after reviewing the plan output**

Run:

```bash
C:\Python312\python.exe -m icewine_cli odds-source the-odds-api-fetch --season 2026 --max-matches 2 --request-budget 5
```

Expected: At most 2 matches processed. New rows, if any, use `source_name=the_odds_api` and `bookmaker=pinnacle`.

- [ ] **Step 5: Inspect written rows without printing API keys**

Run:

```bash
C:\Python312\python.exe -m icewine_cli odds-source the-odds-api-match-report --match-id <match_id_from_fetch_output>
```

Expected: Report shows Pinnacle snapshots from `the_odds_api`, including match winner, asian handicap, and total goals when available.

- [ ] **Step 6: Commit verification fixes if any**

Only if source changes were needed:

```bash
git add <changed files>
git commit -m "fix: stabilize the odds api migration"
```

If no changes were needed, do not create an empty commit.

## Self-Review

- Spec coverage:
  - Independent The Odds API storage is covered by Tasks 2 and 3.
  - No overwrite behavior is covered by Task 1 priority filtering and Task 3 existing-snapshot skip.
  - Source-priority reads are covered by Tasks 1, 5, and 6.
  - CLI shape is covered by Task 4.
  - Error status handling is covered in Task 3.
  - Small live verification is covered by Task 7.
- Placeholder scan:
  - The plan contains no unresolved placeholder steps.
  - Task 3 includes one implementation-choice note for the SQLAlchemy league filter with exact replacement code.
- Type consistency:
  - `THE_ODDS_API_SOURCE_NAME`, `PINNACLE_BOOKMAKER`, and `filter_priority_pinnacle_snapshots` are introduced in Task 1 before downstream use.
  - `map_the_odds_api_event_odds` is introduced in Task 2 before runner use.
  - CLI command functions call public runner functions introduced in Task 3.

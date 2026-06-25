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
        _snapshot(
            match_id,
            event,
            market,
            bookmaker,
            "match_winner",
            "Match Winner",
            Decimal("0.00"),
            side,
            sides[side],
        )
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
        _snapshot(
            match_id,
            event,
            market,
            bookmaker,
            "asian_handicap",
            "Asian Handicap",
            home_line,
            "home",
            by_side["home"],
        ),
        _snapshot(
            match_id,
            event,
            market,
            bookmaker,
            "asian_handicap",
            "Asian Handicap",
            home_line,
            "away",
            by_side["away"],
        ),
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
        _snapshot(
            match_id,
            event,
            market,
            bookmaker,
            "total_goals",
            "Total Goals",
            line,
            "over",
            by_side["over"],
        ),
        _snapshot(
            match_id,
            event,
            market,
            bookmaker,
            "total_goals",
            "Total Goals",
            line,
            "under",
            by_side["under"],
        ),
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
    snapshot_time = _parse_time(
        market.get("last_update") or event.get("last_update") or event.get("commence_time")
    )
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
        raw_payload=json.dumps(
            {"event": event, "market": market, "outcome": outcome},
            sort_keys=True,
        ),
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
    return Decimal(str(value))


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.now(tz=UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)

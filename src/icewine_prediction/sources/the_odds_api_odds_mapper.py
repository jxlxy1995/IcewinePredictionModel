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
    snapshot_time_override: datetime | None = None,
) -> list[HistoricalOddsSnapshotInput]:
    bookmaker_payload = _find_bookmaker(event.get("bookmakers") or [], bookmaker)
    if bookmaker_payload is None:
        return []
    snapshots: list[HistoricalOddsSnapshotInput] = []
    for market in bookmaker_payload.get("markets") or []:
        market_key = str(market.get("key") or "")
        if market_key == "h2h":
            snapshots.extend(_map_h2h(match_id, event, market, bookmaker, snapshot_time_override))
        elif market_key in {"spreads", "alternate_spreads"}:
            snapshots.extend(_map_spreads(match_id, event, market, bookmaker, snapshot_time_override))
        elif market_key in {"totals", "alternate_totals"}:
            snapshots.extend(_map_totals(match_id, event, market, bookmaker, snapshot_time_override))
    return snapshots


def _map_h2h(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
    snapshot_time_override: datetime | None,
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
            snapshot_time_override,
        )
        for side in ("home", "draw", "away")
    ]


def _map_spreads(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
    snapshot_time_override: datetime | None,
) -> list[HistoricalOddsSnapshotInput]:
    home_team = str(event.get("home_team") or "")
    away_team = str(event.get("away_team") or "")
    by_side = {}
    for outcome in market.get("outcomes") or []:
        name = str(outcome.get("name") or "")
        line = _decimal(outcome.get("point"))
        if line is None:
            continue
        if name == home_team:
            by_side.setdefault(line, {})["home"] = outcome
        elif name == away_team:
            by_side.setdefault(-line, {})["away"] = outcome
    snapshots: list[HistoricalOddsSnapshotInput] = []
    for home_line, sides in sorted(by_side.items()):
        if not {"home", "away"}.issubset(sides):
            continue
        snapshots.extend(
            [
                _snapshot(
                    match_id,
                    event,
                    market,
                    bookmaker,
                    "asian_handicap",
                    "Asian Handicap",
                    home_line,
                    "home",
                    sides["home"],
                    snapshot_time_override,
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
                    sides["away"],
                    snapshot_time_override,
                ),
            ]
        )
    return snapshots


def _map_totals(
    match_id: int,
    event: dict[str, Any],
    market: dict[str, Any],
    bookmaker: str,
    snapshot_time_override: datetime | None,
) -> list[HistoricalOddsSnapshotInput]:
    by_side = {}
    for outcome in market.get("outcomes") or []:
        name = str(outcome.get("name") or "").lower()
        line = _decimal(outcome.get("point"))
        if line is None:
            continue
        if name in {"over", "under"}:
            by_side.setdefault(line, {})[name] = outcome
    snapshots: list[HistoricalOddsSnapshotInput] = []
    for line, sides in sorted(by_side.items()):
        if not {"over", "under"}.issubset(sides):
            continue
        snapshots.extend(
            [
                _snapshot(
                    match_id,
                    event,
                    market,
                    bookmaker,
                    "total_goals",
                    "Total Goals",
                    line,
                    "over",
                    sides["over"],
                    snapshot_time_override,
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
                    sides["under"],
                    snapshot_time_override,
                ),
            ]
        )
    return snapshots


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
    snapshot_time_override: datetime | None,
) -> HistoricalOddsSnapshotInput:
    event_id = str(event.get("id") or "")
    market_key = str(market.get("key") or market_type)
    snapshot_time = snapshot_time_override or _parse_time(
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

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
from typing import Any
from zoneinfo import ZoneInfo

from icewine_prediction.sources.oddspapi_market_mapper import map_markets

SELECTED_BOOKMAKERS = {"pinnacle"}
UTC_TIMEZONE = ZoneInfo("UTC")


@dataclass(frozen=True)
class MappedHistoricalOddsSnapshot:
    match_id: int
    source_name: str
    source_fixture_id: str
    bookmaker: str
    market_type: str
    market_id: str
    market_name: str
    market_line: Decimal
    outcome_side: str
    odds: Decimal
    snapshot_time: datetime
    period: str
    raw_payload: str | None = None


def map_historical_odds(
    payload: list[dict[str, Any]] | dict[str, Any],
    match_id: int,
    source_fixture_id: str,
    selected_bookmakers: set[str] | None = None,
    market_definitions: list[dict[str, Any]] | None = None,
) -> list[MappedHistoricalOddsSnapshot]:
    bookmaker_whitelist = selected_bookmakers or SELECTED_BOOKMAKERS
    if isinstance(payload, dict):
        return _map_nested_historical_odds(
            payload=payload,
            match_id=match_id,
            source_fixture_id=source_fixture_id,
            bookmaker_whitelist=bookmaker_whitelist,
            market_definitions=market_definitions or [],
        )
    return _map_flat_historical_odds(
        payload=payload,
        match_id=match_id,
        source_fixture_id=source_fixture_id,
        bookmaker_whitelist=bookmaker_whitelist,
    )


def _map_flat_historical_odds(
    payload: list[dict[str, Any]],
    match_id: int,
    source_fixture_id: str,
    bookmaker_whitelist: set[str],
) -> list[MappedHistoricalOddsSnapshot]:
    snapshots = []
    for bookmaker_item in payload:
        bookmaker = str(bookmaker_item.get("bookmaker", "")).lower()
        if bookmaker not in bookmaker_whitelist:
            continue
        snapshot_time = _parse_snapshot_time(bookmaker_item.get("timestamp"))
        if snapshot_time is None:
            continue
        raw_markets = bookmaker_item.get("markets") or []
        mapped_markets_by_id = {
            market.market_id: market for market in map_markets(raw_markets)
        }
        for raw_market in raw_markets:
            mapped_market = mapped_markets_by_id.get(str(raw_market.get("marketId")))
            if mapped_market is None:
                continue
            for outcome in raw_market.get("outcomes") or []:
                outcome_side = _map_outcome_side(outcome, mapped_market.market_type)
                if outcome_side is None or outcome.get("price") is None:
                    continue
                snapshots.append(
                    MappedHistoricalOddsSnapshot(
                        match_id=match_id,
                        source_name="oddspapi",
                        source_fixture_id=source_fixture_id,
                        bookmaker=bookmaker,
                        market_type=mapped_market.market_type,
                        market_id=mapped_market.market_id,
                        market_name=mapped_market.market_name,
                        market_line=mapped_market.line,
                        outcome_side=outcome_side,
                        odds=Decimal(str(outcome["price"])),
                        snapshot_time=snapshot_time,
                        period=mapped_market.period,
                        raw_payload=json.dumps(raw_market, ensure_ascii=False, sort_keys=True),
                    )
                )
    return snapshots


def _map_nested_historical_odds(
    payload: dict[str, Any],
    match_id: int,
    source_fixture_id: str,
    bookmaker_whitelist: set[str],
    market_definitions: list[dict[str, Any]],
) -> list[MappedHistoricalOddsSnapshot]:
    snapshots = []
    mapped_markets_by_id = {
        market.market_id: market for market in map_markets(market_definitions)
    }
    outcome_names_by_market_and_outcome = _build_outcome_name_map(market_definitions)
    for bookmaker, bookmaker_payload in (payload.get("bookmakers") or {}).items():
        bookmaker = str(bookmaker).lower()
        if bookmaker not in bookmaker_whitelist:
            continue
        for market_id, market_payload in (bookmaker_payload.get("markets") or {}).items():
            mapped_market = mapped_markets_by_id.get(str(market_id))
            if mapped_market is None:
                continue
            outcome_names = outcome_names_by_market_and_outcome.get(str(market_id), {})
            for outcome_id, outcome_payload in (market_payload.get("outcomes") or {}).items():
                outcome_name = outcome_names.get(str(outcome_id), "")
                outcome_side = _map_outcome_side(
                    {"name": outcome_name},
                    mapped_market.market_type,
                )
                if outcome_side is None:
                    continue
                for odds_item in _iter_odds_items(outcome_payload):
                    snapshot_time = _parse_snapshot_time(
                        odds_item.get("createdAt") or odds_item.get("timestamp")
                    )
                    if snapshot_time is None or odds_item.get("price") is None:
                        continue
                    snapshots.append(
                        MappedHistoricalOddsSnapshot(
                            match_id=match_id,
                            source_name="oddspapi",
                            source_fixture_id=source_fixture_id,
                            bookmaker=bookmaker,
                            market_type=mapped_market.market_type,
                            market_id=mapped_market.market_id,
                            market_name=mapped_market.market_name,
                            market_line=mapped_market.line,
                            outcome_side=outcome_side,
                            odds=Decimal(str(odds_item["price"])),
                            snapshot_time=snapshot_time,
                            period=mapped_market.period,
                            raw_payload=json.dumps(
                                odds_item,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        )
                    )
    return snapshots


def _build_outcome_name_map(
    market_definitions: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    names = {}
    for market in market_definitions:
        market_id = str(market.get("marketId"))
        names[market_id] = {
            str(outcome.get("outcomeId")): str(outcome.get("outcomeName", ""))
            for outcome in market.get("outcomes") or []
        }
    return names


def _iter_odds_items(outcome_payload: dict[str, Any]):
    players = outcome_payload.get("players") or {}
    for player_payload in players.values():
        if isinstance(player_payload, list):
            yield from player_payload


def _parse_snapshot_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC_TIMEZONE)
    return parsed.astimezone(UTC_TIMEZONE)


def _map_outcome_side(outcome: dict[str, Any], market_type: str) -> str | None:
    explicit_side = str(outcome.get("side", "")).lower()
    if market_type == "asian_handicap" and explicit_side in {"home", "away"}:
        return explicit_side
    outcome_name = str(outcome.get("name", "")).lower()
    if market_type == "asian_handicap":
        if outcome_name in {"1", "home"}:
            return "home"
        if outcome_name in {"2", "away"}:
            return "away"
    if market_type == "total_goals":
        if "over" in outcome_name:
            return "over"
        if "under" in outcome_name:
            return "under"
    return None

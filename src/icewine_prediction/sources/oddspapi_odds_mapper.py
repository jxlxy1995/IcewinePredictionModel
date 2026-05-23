from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
from typing import Any
from zoneinfo import ZoneInfo

from icewine_prediction.sources.oddspapi_market_mapper import map_markets

SELECTED_BOOKMAKERS = {"pinnacle", "bet365", "sbobet"}
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
    payload: list[dict[str, Any]],
    match_id: int,
    source_fixture_id: str,
    selected_bookmakers: set[str] | None = None,
) -> list[MappedHistoricalOddsSnapshot]:
    bookmaker_whitelist = selected_bookmakers or SELECTED_BOOKMAKERS
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
    if market_type == "total_goals":
        if "over" in outcome_name:
            return "over"
        if "under" in outcome_name:
            return "under"
    return None

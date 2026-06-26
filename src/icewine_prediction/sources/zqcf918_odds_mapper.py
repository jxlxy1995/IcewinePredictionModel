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
            if _is_sealed(row, payload.market):
                continue
            if payload.market == "asian_handicap":
                snapshots.extend(
                    _map_two_way(
                        match_id,
                        source_fixture_id,
                        payload.market,
                        "Asian Handicap",
                        row,
                        "home",
                        "away",
                    )
                )
            elif payload.market == "total_goals":
                snapshots.extend(
                    _map_two_way(
                        match_id,
                        source_fixture_id,
                        payload.market,
                        "Total Goals",
                        row,
                        "over",
                        "under",
                    )
                )
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
        _snapshot(
            match_id,
            source_fixture_id,
            market_type,
            market_name,
            line,
            left_side,
            left_odds,
            snapshot_time,
            row,
        ),
        _snapshot(
            match_id,
            source_fixture_id,
            market_type,
            market_name,
            line,
            right_side,
            right_odds,
            snapshot_time,
            row,
        ),
    ]


def _map_match_winner(
    match_id: int,
    source_fixture_id: str,
    row: dict[str, Any],
) -> list[HistoricalOddsSnapshotInput]:
    snapshot_time = _parse_time(row)
    odds_by_side = {
        "home": _decimal(row.get("c1"), places="0.001"),
        "draw": _decimal(row.get("c2"), places="0.001"),
        "away": _decimal(row.get("c3"), places="0.001"),
    }
    if snapshot_time is None or any(value is None for value in odds_by_side.values()):
        return []
    return [
        _snapshot(
            match_id,
            source_fixture_id,
            "match_winner",
            "Match Winner",
            Decimal("0.00"),
            side,
            odds,
            snapshot_time,
            row,
        )
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


def _is_sealed(row: dict[str, Any], market: str) -> bool:
    if row.get("isFeng2") is True:
        return True
    if market == "match_winner":
        values = (row.get("c1"), row.get("c2"), row.get("c3"))
    else:
        values = (row.get("c"), row.get("d"), row.get("e"))
    return any(str(value).strip() in {"", "封", "-", "None"} for value in values)


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

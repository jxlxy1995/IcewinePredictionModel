from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from icewine_prediction.feature_service import is_standard_market_line


@dataclass(frozen=True)
class MappedOddsMarket:
    market_id: str
    market_type: str
    market_name: str
    line: Decimal
    period: str
    outcome_ids: tuple[str, ...] = ()


def map_markets(payload: list[dict[str, Any]]) -> list[MappedOddsMarket]:
    mapped = []
    for item in payload:
        if item.get("period") != "fulltime":
            continue
        market_type = _map_market_type(item.get("marketType"))
        if market_type is None:
            continue
        line = Decimal(str(item.get("handicap")))
        if not is_standard_market_line(line):
            continue
        mapped.append(
            MappedOddsMarket(
                market_id=str(item["marketId"]),
                market_type=market_type,
                market_name=item["marketName"],
                line=line,
                period=item["period"],
                outcome_ids=tuple(
                    str(outcome.get("outcomeId"))
                    for outcome in item.get("outcomes") or []
                    if outcome.get("outcomeId") is not None
                ),
            )
        )
    return mapped


def _map_market_type(source_market_type: str | None) -> str | None:
    if source_market_type == "spreads":
        return "asian_handicap"
    if source_market_type == "totals":
        return "total_goals"
    return None

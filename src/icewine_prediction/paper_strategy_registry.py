from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY = "asian_away_cover_hgb_edge_v1"
ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME = "亚盘客队方向 · HGB边际 v1"
ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY = "asian_away_cover_hgb_bucket_v2"
ASIAN_AWAY_COVER_HGB_BUCKET_V2_NAME = "亚盘客队方向 · HGB分盘口桶 v2"
DEFAULT_MODEL_NAME = "raw_hgb_team_form_plus_all_markets"
DEFAULT_SIGNAL_VERSION = "v1"


@dataclass(frozen=True)
class PaperStrategy:
    strategy_key: str
    display_name: str
    market_type: str
    side: str
    edge_threshold: Decimal
    model_name: str
    signal_version: str
    line_bucket_thresholds: dict[str, Decimal] | None = None
    risk_tag: str | None = None


DEFAULT_STRATEGY = PaperStrategy(
    strategy_key=ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    display_name=ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    market_type="asian_handicap",
    side="away_cover",
    edge_threshold=Decimal("0.1000"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version=DEFAULT_SIGNAL_VERSION,
)
BUCKET_V2_STRATEGY = PaperStrategy(
    strategy_key=ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY,
    display_name=ASIAN_AWAY_COVER_HGB_BUCKET_V2_NAME,
    market_type="asian_handicap",
    side="away_cover",
    edge_threshold=Decimal("0.0800"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version="v2",
    line_bucket_thresholds={
        "away_underdog": Decimal("0.2000"),
        "pickem": Decimal("0.0800"),
    },
    risk_tag="strategy:bucket_v2",
)
STRATEGIES = (DEFAULT_STRATEGY, BUCKET_V2_STRATEGY)


def strategy_for_key(strategy_key: str) -> PaperStrategy | None:
    return next((strategy for strategy in STRATEGIES if strategy.strategy_key == strategy_key), None)

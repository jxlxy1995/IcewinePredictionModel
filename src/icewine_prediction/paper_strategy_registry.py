from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY = "asian_away_cover_hgb_edge_v1"
ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME = "亚盘客队方向 · HGB边际 v1"
ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY = "asian_away_cover_hgb_bucket_v2"
ASIAN_AWAY_COVER_HGB_BUCKET_V2_NAME = "亚盘客队方向 · HGB分盘口桶 v2"
ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY = "asian_home_cover_hgb_favorite_bucket_v1"
ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME = "亚盘主队让球方向 · HGB分盘口桶 v1"
TOTAL_GOALS_HGB_BUCKET_V2_KEY = "total_goals_hgb_bucket_v2"
TOTAL_GOALS_HGB_BUCKET_V2_NAME = "大小球方向 · HGB分盘口桶 v2"
TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_KEY = "total_goals_hgb_low_line_bucket_v3"
TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_NAME = "大小球低盘口方向 · HGB分盘口桶 v3"
TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY = "total_goals_hgb_confirmed_under_mid_275_v1"
TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_NAME = "大小球小球方向 · HGB模型共识 v1"
DEFAULT_MODEL_NAME = "raw_hgb_team_form_plus_all_markets"
DEFAULT_SIGNAL_VERSION = "v1"


# New paper strategies should not be promoted into live recommendation flow
# from raw ROI alone. Before adding or enabling a strategy here, run the
# robustness filter report and review raw, T-15, robust kept, and filtered
# performance. See docs/交接/20260603-paper-strategy-research-checklist.md.
@dataclass(frozen=True)
class PaperStrategy:
    strategy_key: str
    display_name: str
    market_type: str
    side: str | None
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
        "away_favorite": Decimal("0.1500"),
        "away_underdog": Decimal("0.2000"),
        "pickem": Decimal("0.0800"),
    },
    risk_tag="strategy:bucket_v2",
)
HOME_FAVORITE_BUCKET_V1_STRATEGY = PaperStrategy(
    strategy_key=ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
    display_name=ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME,
    market_type="asian_handicap",
    side="home_cover",
    edge_threshold=Decimal("0.1500"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version="v1",
    line_bucket_thresholds={
        "home_favorite": Decimal("0.1500"),
    },
    risk_tag="strategy:asian_home_favorite_bucket_v1",
)
TOTAL_GOALS_BUCKET_V2_STRATEGY = PaperStrategy(
    strategy_key=TOTAL_GOALS_HGB_BUCKET_V2_KEY,
    display_name=TOTAL_GOALS_HGB_BUCKET_V2_NAME,
    market_type="total_goals",
    side=None,
    edge_threshold=Decimal("0.0800"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version="v2",
    line_bucket_thresholds={
        "over@mid_2.75": Decimal("0.0800"),
        "under@mid_2.75": Decimal("0.0800"),
    },
    risk_tag="strategy:total_goals_bucket_v2",
)
TOTAL_GOALS_LOW_LINE_BUCKET_V3_STRATEGY = PaperStrategy(
    strategy_key=TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_KEY,
    display_name=TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_NAME,
    market_type="total_goals",
    side=None,
    edge_threshold=Decimal("0.0600"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version="v3",
    line_bucket_thresholds={
        "over@low_<=2.25": Decimal("0.0600"),
        "under@low_<=2.25": Decimal("0.1200"),
    },
    risk_tag="strategy:total_goals_low_line_bucket_v3",
)
TOTAL_GOALS_CONFIRMED_UNDER_MID_275_V1_STRATEGY = PaperStrategy(
    strategy_key=TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY,
    display_name=TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_NAME,
    market_type="total_goals",
    side="under",
    edge_threshold=Decimal("0.1500"),
    model_name=DEFAULT_MODEL_NAME,
    signal_version="v1",
    line_bucket_thresholds={
        "under@mid_2.75": Decimal("0.1500"),
    },
    risk_tag="strategy:total_goals_confirmed_under_mid_275_v1",
)
STRATEGIES = (
    DEFAULT_STRATEGY,
    BUCKET_V2_STRATEGY,
    HOME_FAVORITE_BUCKET_V1_STRATEGY,
    TOTAL_GOALS_BUCKET_V2_STRATEGY,
    TOTAL_GOALS_LOW_LINE_BUCKET_V3_STRATEGY,
    TOTAL_GOALS_CONFIRMED_UNDER_MID_275_V1_STRATEGY,
)


def strategy_for_key(strategy_key: str) -> PaperStrategy | None:
    return next((strategy for strategy in STRATEGIES if strategy.strategy_key == strategy_key), None)

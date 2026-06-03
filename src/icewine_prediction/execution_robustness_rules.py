from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from icewine_prediction.paper_strategy_registry import (
    ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY,
    ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
    TOTAL_GOALS_HGB_BUCKET_V2_KEY,
    TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_KEY,
)


@dataclass(frozen=True)
class SelectedExecutionRobustnessRule:
    strategy_key: str
    primary_target: int
    min_seen_count: int
    min_edge: Decimal
    allow_bucket_changed: bool
    allow_line_changed: bool
    require_side_unchanged: bool
    mode: str = "filter"

    def as_grid_rule(self):
        from icewine_prediction.baseline_execution_robustness_grid_service import (
            ExecutionRobustnessGridRule,
        )

        return ExecutionRobustnessGridRule(
            min_seen_count=self.min_seen_count,
            min_edge=self.min_edge,
            allow_bucket_changed=self.allow_bucket_changed,
            allow_line_changed=self.allow_line_changed,
            require_side_unchanged=self.require_side_unchanged,
        )


DEFAULT_SELECTED_ROBUSTNESS_RULES: dict[str, SelectedExecutionRobustnessRule] = {
    ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY: SelectedExecutionRobustnessRule(
        strategy_key=ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
        primary_target=10,
        min_seen_count=5,
        min_edge=Decimal("0.0800"),
        allow_bucket_changed=False,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
    ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY: SelectedExecutionRobustnessRule(
        strategy_key=ASIAN_AWAY_COVER_HGB_BUCKET_V2_KEY,
        primary_target=10,
        min_seen_count=4,
        min_edge=Decimal("0.1200"),
        allow_bucket_changed=False,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY: SelectedExecutionRobustnessRule(
        strategy_key=ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
        primary_target=10,
        min_seen_count=4,
        min_edge=Decimal("0.0800"),
        allow_bucket_changed=False,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
    TOTAL_GOALS_HGB_BUCKET_V2_KEY: SelectedExecutionRobustnessRule(
        strategy_key=TOTAL_GOALS_HGB_BUCKET_V2_KEY,
        primary_target=10,
        min_seen_count=2,
        min_edge=Decimal("0.1200"),
        allow_bucket_changed=True,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
    TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_KEY: SelectedExecutionRobustnessRule(
        strategy_key=TOTAL_GOALS_HGB_LOW_LINE_BUCKET_V3_KEY,
        primary_target=10,
        min_seen_count=3,
        min_edge=Decimal("0.1200"),
        allow_bucket_changed=True,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
}

from decimal import Decimal

from icewine_prediction.execution_robustness_rules import DEFAULT_SELECTED_ROBUSTNESS_RULES
from icewine_prediction.paper_strategy_registry import STRATEGIES, strategy_for_key


def test_new_total_goals_paper_strategies_are_registered_with_robustness_rules():
    expected_rules = {
        "total_goals_distribution_hgb_confirmed_under_high_300_v1": {
            "display_name": "大小球高盘小球方向 · 分布模型+HGB确认 v1",
            "seen": 4,
            "edge": Decimal("0.0000"),
            "allow_bucket": False,
            "allow_line": False,
        },
        "total_goals_distribution_hgb_confirmed_over_mid_250_v1": {
            "display_name": "大小球2.50大球方向 · 分布模型+HGB确认 v1",
            "seen": 3,
            "edge": Decimal("0.0000"),
            "allow_bucket": True,
            "allow_line": True,
        },
        "total_goals_hgb_confirmed_under_low_225_v1": {
            "display_name": "大小球低盘小球方向 · HGB确认 v1",
            "seen": 2,
            "edge": Decimal("0.0400"),
            "allow_bucket": True,
            "allow_line": True,
        },
    }

    assert expected_rules.keys() <= {strategy.strategy_key for strategy in STRATEGIES}
    for strategy_key, expected in expected_rules.items():
        strategy = strategy_for_key(strategy_key)
        rule = DEFAULT_SELECTED_ROBUSTNESS_RULES[strategy_key]

        assert strategy is not None
        assert strategy.market_type == "total_goals"
        assert strategy.display_name == expected["display_name"]
        assert rule.primary_target == 10
        assert rule.min_seen_count == expected["seen"]
        assert rule.min_edge == expected["edge"]
        assert rule.allow_bucket_changed == expected["allow_bucket"]
        assert rule.allow_line_changed == expected["allow_line"]
        assert rule.require_side_unchanged is True

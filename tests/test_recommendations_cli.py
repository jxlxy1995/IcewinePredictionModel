from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_recommendation_line
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.recommendation_service import Recommendation


def test_recommendations_group_exposes_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["recommendations", "--help"])

    assert result.exit_code == 0
    assert "preview" in result.stdout


def test_format_recommendation_line_uses_chinese_match_and_recommendation_text():
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Serie A": "意甲"},
            teams={"Bologna": "博洛尼亚", "Inter": "国际米兰"},
        )
    )
    match = SimpleNamespace(
        kickoff_time=datetime(2026, 5, 24, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league=SimpleNamespace(name="Serie A"),
        home_team=SimpleNamespace(canonical_name="Bologna"),
        away_team=SimpleNamespace(canonical_name="Inter"),
    )
    recommendations = [
        Recommendation(
            market_type="asian_handicap",
            side="home",
            confidence_grade="B",
            stake_units=Decimal("1.25"),
            should_bet=True,
            edge=Decimal("0.063"),
            risk_tags=[],
            model_probability=Decimal("0.5700"),
            market_implied_probability=Decimal("0.5070"),
            similar_backtest_roi=Decimal("0.05"),
            home_expected_goals=Decimal("1.80"),
            away_expected_goals=Decimal("1.00"),
            market_line=Decimal("-0.25"),
        ),
        Recommendation(
            market_type="total_goals",
            side="watch",
            confidence_grade="D",
            stake_units=Decimal("0"),
            should_bet=False,
            edge=Decimal("0"),
            risk_tags=["weak_market_signal"],
        ),
    ]

    line = format_recommendation_line(match, recommendations, display_service)
    assert "线 -0.25" in line
    assert "模型概率 0.5700" in line
    assert "隐含概率 0.5070" in line
    assert "edge 0.063" in line
    assert "期望进球 1.80-1.00" in line

    assert "意甲 2026-05-24 00:00 博洛尼亚 vs 国际米兰" in line
    assert "亚盘 主队 B 1.25手" in line
    assert "大小球 观望 D 0手" in line
    assert "weak_market_signal" in line

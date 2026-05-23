from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_feature_line
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.feature_service import MatchOddsFeatures, OddsMarketAggregate


def _aggregate(value: str, sample_count: int = 3, disagreement: str = "0.25"):
    decimal_value = Decimal(value)
    return OddsMarketAggregate(
        sample_count=sample_count,
        mean=decimal_value,
        median=decimal_value,
        minimum=decimal_value,
        maximum=decimal_value,
        disagreement=Decimal(disagreement),
    )


def test_features_group_exposes_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["features", "--help"])

    assert result.exit_code == 0
    assert "preview" in result.stdout


def test_format_feature_line_uses_chinese_names_and_market_consensus():
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
    features = MatchOddsFeatures(
        match_id=1,
        bookmaker_count=12,
        asian_handicap=_aggregate("0.25", sample_count=10, disagreement="0.25"),
        home_odds=_aggregate("1.98", sample_count=10, disagreement="0.20"),
        away_odds=_aggregate("1.88", sample_count=10, disagreement="0.18"),
        total_line=_aggregate("2.75", sample_count=12, disagreement="0.50"),
        over_odds=_aggregate("1.91", sample_count=12, disagreement="0.30"),
        under_odds=_aggregate("1.93", sample_count=12, disagreement="0.28"),
    )

    line = format_feature_line(match, features, display_service)

    assert "意甲 2026-05-24 00:00 博洛尼亚 vs 国际米兰" in line
    assert "亚盘均值 0.25" in line
    assert "大小球均值 2.75" in line
    assert "bookmaker 12" in line

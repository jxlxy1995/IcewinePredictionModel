from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_training_sample_line
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.training_sample_service import TrainingSample


def test_samples_group_exposes_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "preview" in result.stdout


def test_format_training_sample_line_uses_chinese_match_names_and_labels():
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"La Liga": "西甲"},
            teams={"Real Madrid": "皇家马德里", "Barcelona": "巴塞罗那"},
        )
    )
    sample = TrainingSample(
        match_id=1,
        source_match_id="3001",
        league_name="La Liga",
        home_team_name="Real Madrid",
        away_team_name="Barcelona",
        kickoff_time=datetime(2025, 5, 25, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=2,
        away_score=1,
        match_result="home_win",
        total_goals=3,
        asian_handicap_line=None,
        home_handicap_result=None,
        away_handicap_result=None,
        total_line=None,
        over_result=None,
        under_result=None,
        has_odds_snapshot=False,
        sample_age_days=363,
        time_decay_weight=Decimal("0.80"),
    )

    line = format_training_sample_line(sample, display_service)

    assert "西甲 2025-05-25 03:00 皇家马德里 vs 巴塞罗那" in line
    assert "比分 2-1" in line
    assert "赛果 home_win" in line
    assert "样本年龄 363天" in line
    assert "权重 0.80" in line
    assert "赔率 否" in line

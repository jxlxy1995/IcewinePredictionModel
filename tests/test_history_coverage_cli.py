from decimal import Decimal

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_history_coverage_report
from icewine_prediction.history_coverage_service import LeagueCoverageSummary


def test_history_group_exposes_coverage_help():
    runner = CliRunner()

    result = runner.invoke(app, ["history", "coverage", "--help"])

    assert result.exit_code == 0
    assert "coverage" in result.output


def test_format_history_coverage_report_outputs_chinese_summary():
    summary = LeagueCoverageSummary(
        league_name="La Liga",
        country_or_region="Spain",
        total_matches=380,
        finished_matches=379,
        scored_matches=379,
        matches_with_odds=300,
        matches_with_asian_handicap=290,
        matches_with_total_goals=285,
        odds_coverage_ratio=Decimal("0.7895"),
        asian_handicap_coverage_ratio=Decimal("0.7632"),
        total_goals_coverage_ratio=Decimal("0.7500"),
    )

    text = format_history_coverage_report([summary])

    assert "La Liga" in text
    assert "总比赛 380" in text
    assert "赔率覆盖 0.7895" in text
    assert "亚盘覆盖 0.7632" in text
    assert "大小球覆盖 0.7500" in text

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import (
    app,
    format_historical_odds_market_feature_line,
    format_historical_market_training_sample_line,
    format_training_sample_line,
)
from icewine_prediction.close_market_baseline_service import (
    CloseMarketBaselineMarketReport,
    CloseMarketBaselineReport,
)
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.historical_odds_feature_service import HistoricalOddsMarketFeature
from icewine_prediction.historical_training_sample_service import (
    HistoricalMarketTrainingSample,
    HistoricalOddsAnchorFeature,
)
from icewine_prediction.historical_training_sample_report_service import (
    HistoricalOddsSampleQualityReport,
)
from icewine_prediction.training_sample_service import TrainingSample


def test_samples_group_exposes_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "preview" in result.stdout


def test_samples_group_exposes_historical_odds_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "historical-odds-preview" in result.stdout


def test_samples_group_exposes_historical_odds_report_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "historical-odds-report" in result.stdout


def test_samples_group_exposes_historical_odds_features_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "historical-odds-features-preview" in result.stdout


def test_samples_group_exposes_historical_odds_close_baseline_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "historical-odds-close-baseline" in result.stdout


def test_format_training_sample_line_uses_match_result_and_weight():
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

    assert "2025-05-25 03:00" in line
    assert "2-1" in line
    assert "home_win" in line
    assert "363" in line
    assert "0.80" in line


def test_format_historical_market_training_sample_line_summarizes_anchor_coverage():
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Premier League": "英超"},
            teams={"Arsenal": "阿森纳", "Chelsea": "切尔西"},
        )
    )
    sample = _historical_market_sample(
        market_type="asian_handicap",
        snapshot_count=30,
        missing_anchor_labels=("12h",),
        quality_tags=("thin_history",),
    )

    line = format_historical_market_training_sample_line(sample, display_service)

    assert "英超 2026-05-20 20:00 阿森纳 vs 切尔西" in line
    assert "asian_handicap" in line
    assert "锚点 2/7 24h/close" in line
    assert "缺失 12h" in line
    assert "标签 thin_history" in line


def test_format_historical_odds_market_feature_line_summarizes_close_probability():
    display_service = DisplayNameService(
        DisplayNames(
            leagues={"Premier League": "英超"},
            teams={"Arsenal": "阿森纳", "Chelsea": "切尔西"},
        )
    )
    feature = _historical_market_feature()

    line = format_historical_odds_market_feature_line(feature, display_service)

    assert "英超 2026-05-20 20:00 阿森纳 vs 切尔西" in line
    assert "match_winner" in line
    assert "锚点 24h->close" in line
    assert "close 0.5556/0.2500/0.2000" in line
    assert "prob变化 0.0556/0.0000/-0.0500" in line


def test_samples_historical_odds_preview_command_outputs_samples(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_historical_market_training_samples",
        lambda session, season, limit, bookmaker: [
            _historical_market_sample(
                market_type="total_goals",
                snapshot_count=40,
                missing_anchor_labels=(),
                quality_tags=(),
            )
        ],
    )

    result = runner.invoke(
        app,
        ["samples", "historical-odds-preview", "--season", "2026", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "total_goals" in result.stdout
    assert "锚点 2/7 24h/close" in result.stdout


def test_samples_historical_odds_report_command_outputs_quality_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build_report(session, *, season, eligible_start, bookmaker):
        captured["season"] = season
        captured["eligible_start"] = eligible_start
        captured["bookmaker"] = bookmaker
        return HistoricalOddsSampleQualityReport(
            season=season,
            eligible_start=eligible_start,
            bookmaker=bookmaker,
            full_season_match_count=3,
            eligible_match_count=2,
            excluded_before_eligible_start_count=1,
            match_with_sample_count=1,
            eligible_coverage_ratio=Decimal("0.5000"),
            full_season_coverage_ratio=Decimal("0.3333"),
            market_reports={},
            league_reports={},
        )

    monkeypatch.setattr(
        "icewine_prediction.cli.build_historical_odds_sample_quality_report",
        fake_build_report,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "historical-odds-report",
            "--season",
            "2026",
            "--eligible-start",
            "2026-01-15",
        ],
    )

    assert result.exit_code == 0
    assert captured["season"] == 2026
    assert captured["bookmaker"] == "pinnacle"
    assert captured["eligible_start"].strftime("%Y-%m-%d %H:%M") == "2026-01-15 00:00"
    assert "eligible coverage 0.5000" in result.stdout
    assert "full-season coverage 0.3333" in result.stdout


def test_samples_historical_odds_features_preview_command_outputs_features(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "icewine_prediction.cli.list_historical_odds_market_features",
        lambda session, season, limit, bookmaker: [_historical_market_feature()],
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "historical-odds-features-preview",
            "--season",
            "2026",
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "match_winner" in result.stdout
    assert "close 0.5556/0.2500/0.2000" in result.stdout


def test_samples_historical_odds_close_baseline_command_outputs_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build_report(session, *, season, limit, bookmaker):
        captured["season"] = season
        captured["limit"] = limit
        captured["bookmaker"] = bookmaker
        return CloseMarketBaselineReport(
            total_feature_count=1,
            evaluated_sample_count=1,
            skipped_sample_count=0,
            market_reports={
                "match_winner": CloseMarketBaselineMarketReport(
                    market_type="match_winner",
                    feature_count=1,
                    evaluated_sample_count=1,
                    skipped_sample_count=0,
                    average_log_loss=Decimal("0.5920"),
                    average_brier_score=Decimal("0.2900"),
                    accuracy=Decimal("1.0000"),
                    average_overround=Decimal("1.0056"),
                )
            },
        )

    monkeypatch.setattr(
        "icewine_prediction.cli.build_close_market_baseline_report_from_session",
        fake_build_report,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "historical-odds-close-baseline",
            "--season",
            "2026",
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["season"] == 2026
    assert captured["limit"] == 5
    assert captured["bookmaker"] == "pinnacle"
    assert "close market baseline" in result.stdout
    assert "match_winner: evaluated 1 skipped 0" in result.stdout


def _historical_market_feature() -> HistoricalOddsMarketFeature:
    return HistoricalOddsMarketFeature(
        match_id=1,
        source_match_id="1001",
        league_name="Premier League",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=2,
        away_score=1,
        market_type="match_winner",
        bookmaker="pinnacle",
        opening_anchor_label="24h",
        close_anchor_label="close",
        opening_market_line=Decimal("0.00"),
        close_market_line=Decimal("0.00"),
        line_movement=Decimal("0.00"),
        side_a="home",
        side_b="draw",
        side_c="away",
        opening_side_a_implied_probability=Decimal("0.5000"),
        opening_side_b_implied_probability=Decimal("0.2500"),
        opening_side_c_implied_probability=Decimal("0.2500"),
        close_side_a_implied_probability=Decimal("0.5556"),
        close_side_b_implied_probability=Decimal("0.2500"),
        close_side_c_implied_probability=Decimal("0.2000"),
        side_a_implied_probability_movement=Decimal("0.0556"),
        side_b_implied_probability_movement=Decimal("0.0000"),
        side_c_implied_probability_movement=Decimal("-0.0500"),
        opening_overround=Decimal("1.0000"),
        close_overround=Decimal("1.0056"),
        side_a_odds_movement=Decimal("-0.2000"),
        side_b_odds_movement=Decimal("0.0000"),
        side_c_odds_movement=Decimal("1.0000"),
        close_side_a_result="win",
        close_side_b_result="loss",
        close_side_c_result="loss",
        snapshot_count=60,
        missing_anchor_labels=(),
        quality_tags=(),
    )


def _historical_market_sample(
    *,
    market_type: str,
    snapshot_count: int,
    missing_anchor_labels: tuple[str, ...],
    quality_tags: tuple[str, ...],
) -> HistoricalMarketTrainingSample:
    return HistoricalMarketTrainingSample(
        match_id=1,
        source_match_id="1001",
        league_name="Premier League",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 5, 20, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_score=2,
        away_score=1,
        market_type=market_type,
        bookmaker="pinnacle",
        snapshot_count=snapshot_count,
        anchors=(_anchor("24h", Decimal("-0.25")), _anchor("close", Decimal("-0.50"))),
        missing_anchor_labels=missing_anchor_labels,
        quality_tags=quality_tags,
        line_movement=Decimal("-0.25"),
        side_a_odds_movement=Decimal("-0.0200"),
        side_b_odds_movement=Decimal("0.0300"),
    )


def _anchor(label: str, line: Decimal) -> HistoricalOddsAnchorFeature:
    return HistoricalOddsAnchorFeature(
        label=label,
        target_minutes_before_kickoff=1440 if label == "24h" else 5,
        actual_minutes_before_kickoff=1440 if label == "24h" else 7,
        snapshot_time=datetime(2026, 5, 20, 19, 53, tzinfo=ZoneInfo("Asia/Shanghai")),
        bookmaker="pinnacle",
        market_line=line,
        side_a="home",
        side_b="away",
        side_a_odds=Decimal("1.90"),
        side_b_odds=Decimal("1.96"),
        side_a_implied_probability=Decimal("0.5263"),
        side_b_implied_probability=Decimal("0.5102"),
        overround=Decimal("1.0365"),
        side_a_result="win",
        side_b_result="loss",
    )

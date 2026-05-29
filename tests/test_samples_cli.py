from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import (
    app,
    format_baseline_training_dataset_command_result,
    format_historical_odds_market_feature_line,
    format_historical_market_training_sample_line,
    format_training_sample_line,
)
from icewine_prediction.baseline_training_dataset_service import (
    BaselineTrainingDataset,
    BaselineTrainingDatasetAudit,
)
from icewine_prediction.baseline_training_dataset_qa_service import (
    BaselineTrainingDatasetQaReport,
)
from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    BaselineTrainingDatasetMarketBaselineReport,
    MarketBaselineReport,
)
from icewine_prediction.baseline_feature_set_service import (
    BaselineFeatureSet,
    BaselineFeatureSetReport,
)
from icewine_prediction.baseline_asian_handicap_model_service import (
    AsianHandicapModelEvaluation,
    BaselineAsianHandicapModelReport,
    CloseMarketAsianHandicapReference,
)
from icewine_prediction.baseline_match_winner_model_service import (
    BaselineMatchWinnerModelReport,
    CalibrationBucket,
    CloseMarketMatchWinnerReference,
    MatchWinnerModelEvaluation,
)
from icewine_prediction.baseline_market_diagnostics_service import (
    BaselineMarketDiagnosticsReport,
    MarketDiagnostics,
    SegmentDiagnostics,
)
from icewine_prediction.baseline_total_goals_model_service import (
    BaselineTotalGoalsModelReport,
    CloseMarketTotalGoalsReference,
    TotalGoalsModelEvaluation,
)
from icewine_prediction.close_market_baseline_service import (
    CloseMarketBaselineMarketReport,
    CloseMarketBaselineReport,
)
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.historical_odds_feature_service import HistoricalOddsMarketFeature
from icewine_prediction.historical_odds_anchor_coverage_service import (
    AnchorCoverage,
    HistoricalOddsAnchorCoverageReport,
    MarketAnchorCoverageReport,
)
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


def test_samples_group_exposes_historical_odds_anchor_coverage_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "historical-odds-anchor-coverage" in result.stdout


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


def test_samples_group_exposes_baseline_dataset_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-dataset" in result.stdout


def test_samples_group_exposes_baseline_dataset_qa_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-dataset-qa" in result.stdout


def test_samples_group_exposes_baseline_market_baseline_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-market-baseline" in result.stdout


def test_samples_group_exposes_baseline_feature_set_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-feature-set" in result.stdout


def test_samples_group_exposes_baseline_match_winner_model_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-match-winner-model" in result.stdout


def test_samples_group_exposes_baseline_asian_handicap_model_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-asian-handicap-model" in result.stdout


def test_samples_group_exposes_baseline_total_goals_model_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-total-goals-model" in result.stdout


def test_samples_group_exposes_baseline_market_diagnostics_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-market-diagnostics" in result.stdout


def test_format_baseline_training_dataset_command_result_summarizes_outputs():
    text = format_baseline_training_dataset_command_result(
        dataset_path="local_data/training/baseline.csv",
        report_path="docs/团队协作/baseline.md",
        dataset=_baseline_dataset(),
    )

    assert "baseline dataset written" in text
    assert "local_data/training/baseline.csv" in text
    assert "docs/团队协作/baseline.md" in text
    assert "rows 1/2" in text
    assert "coverage 0.5000" in text


def test_samples_baseline_dataset_command_writes_dataset_and_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(session, *, eligible_start, source_name, bookmaker):
        captured["eligible_start"] = eligible_start
        captured["source_name"] = source_name
        captured["bookmaker"] = bookmaker
        return _baseline_dataset()

    def fake_write_csv(dataset, output_path):
        captured["dataset_path"] = str(output_path)

    def fake_write_report(audit, output_path):
        captured["report_path"] = str(output_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_training_dataset",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_training_dataset_csv",
        fake_write_csv,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_training_dataset_report",
        fake_write_report,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-dataset",
            "--output-path",
            "local_data/training/test.csv",
            "--report-path",
            "docs/团队协作/test.md",
            "--eligible-start",
            "2026-01-15",
        ],
    )

    assert result.exit_code == 0
    assert captured["source_name"] == "oddspapi"
    assert captured["bookmaker"] == "pinnacle"
    assert captured["eligible_start"].strftime("%Y-%m-%d %H:%M") == "2026-01-15 00:00"
    assert captured["dataset_path"].endswith("local_data\\training\\test.csv")
    assert captured["report_path"].endswith("docs\\团队协作\\test.md")
    assert "rows 1/2" in result.stdout


def test_samples_baseline_dataset_qa_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, low_sample_threshold=30):
        captured["csv_path"] = str(csv_path)
        captured["low_sample_threshold"] = low_sample_threshold
        return _baseline_qa_report()

    def fake_write(report, output_path):
        captured["output_path"] = str(output_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_training_dataset_qa_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_training_dataset_qa_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-dataset-qa",
            "--csv-path",
            "local_data/training/baseline.csv",
            "--report-path",
            "docs/团队协作/baseline-qa.md",
            "--low-sample-threshold",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("docs\\团队协作\\baseline-qa.md")
    assert captured["low_sample_threshold"] == 25
    assert "baseline dataset QA written" in result.stdout
    assert "rows 1" in result.stdout
    assert "thin-history 0" in result.stdout


def test_samples_baseline_market_baseline_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path):
        captured["csv_path"] = str(csv_path)
        return _baseline_market_report()

    def fake_write(report, output_path):
        captured["output_path"] = str(output_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_training_dataset_market_baseline_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_training_dataset_market_baseline_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-market-baseline",
            "--csv-path",
            "local_data/training/baseline.csv",
            "--report-path",
            "docs/团队协作/market-baseline.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("docs\\团队协作\\market-baseline.md")
    assert "close-market baseline written" in result.stdout
    assert "evaluated 3/3" in result.stdout


def test_samples_historical_odds_anchor_coverage_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(session, *, season, eligible_start, bookmaker):
        captured["season"] = season
        captured["eligible_start"] = eligible_start
        captured["bookmaker"] = bookmaker
        return _historical_odds_anchor_coverage_report()

    def fake_write(report, output_path):
        captured["output_path"] = str(output_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_historical_odds_anchor_coverage_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_historical_odds_anchor_coverage_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "historical-odds-anchor-coverage",
            "--season",
            "2026",
            "--eligible-start",
            "2026-01-15",
            "--bookmaker",
            "pinnacle",
            "--report-path",
            "docs/团队协作/anchor.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["season"] == 2026
    assert captured["bookmaker"] == "pinnacle"
    assert captured["eligible_start"].strftime("%Y-%m-%d") == "2026-01-15"
    assert captured["output_path"].endswith("docs\\团队协作\\anchor.md")
    assert "historical odds anchor coverage written" in result.stdout
    assert "asian_handicap samples 10 complete-core 8" in result.stdout


def test_samples_baseline_feature_set_command_writes_csv_and_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, validation_ratio):
        captured["csv_path"] = str(csv_path)
        captured["validation_ratio"] = validation_ratio
        return _baseline_feature_set()

    def fake_write_csv(feature_set, output_path):
        captured["output_path"] = str(output_path)

    def fake_write_report(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr("icewine_prediction.cli.build_baseline_feature_set", fake_build)
    monkeypatch.setattr("icewine_prediction.cli.write_baseline_feature_set_csv", fake_write_csv)
    monkeypatch.setattr("icewine_prediction.cli.write_baseline_feature_set_report", fake_write_report)

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-feature-set",
            "--csv-path",
            "local_data/training/baseline.csv",
            "--output-path",
            "local_data/training/features.csv",
            "--report-path",
            "docs/团队协作/features.md",
            "--validation-ratio",
            "0.25",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\团队协作\\features.md")
    assert captured["validation_ratio"] == "0.25"
    assert "baseline feature set written" in result.stdout
    assert "rows 4 train 3 validation 1" in result.stdout


def test_samples_baseline_match_winner_model_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path):
        captured["csv_path"] = str(csv_path)
        return _baseline_match_winner_model_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_match_winner_model_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_match_winner_model_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-match-winner-model",
            "--csv-path",
            "local_data/training/features.csv",
            "--report-path",
            "docs/团队协作/match-winner.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\团队协作\\match-winner.md")
    assert "baseline match winner model written" in result.stdout
    assert "team_form_only log-loss 1.0000" in result.stdout


def test_samples_baseline_asian_handicap_model_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path):
        captured["csv_path"] = str(csv_path)
        return _baseline_asian_handicap_model_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_asian_handicap_model_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_asian_handicap_model_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-asian-handicap-model",
            "--csv-path",
            "local_data/training/features.csv",
            "--report-path",
            "docs/团队协作/asian-handicap.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\团队协作\\asian-handicap.md")
    assert "baseline asian handicap model written" in result.stdout
    assert "team_form_plus_all_markets log-loss 0.7000" in result.stdout


def test_samples_baseline_total_goals_model_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path):
        captured["csv_path"] = str(csv_path)
        return _baseline_total_goals_model_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_total_goals_model_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_total_goals_model_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-total-goals-model",
            "--csv-path",
            "local_data/training/features.csv",
            "--report-path",
            "docs/鍥㈤槦鍗忎綔/total-goals.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\鍥㈤槦鍗忎綔\\total-goals.md")
    assert "baseline total goals model written" in result.stdout
    assert "team_form_plus_all_markets log-loss 0.7000" in result.stdout


def test_samples_baseline_market_diagnostics_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path):
        captured["csv_path"] = str(csv_path)
        return _baseline_market_diagnostics_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_market_diagnostics_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_market_diagnostics_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-market-diagnostics",
            "--csv-path",
            "local_data/training/features.csv",
            "--report-path",
            "docs/团队协作/diagnostics.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\团队协作\\diagnostics.md")
    assert "baseline market diagnostics written" in result.stdout
    assert "asian_handicap accuracy 0.6000 rows 10" in result.stdout
    assert "total_goals accuracy 0.5000 rows 8" in result.stdout


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


def _baseline_dataset() -> BaselineTrainingDataset:
    return BaselineTrainingDataset(
        rows=[{"match_id": "1"}],
        audit=BaselineTrainingDatasetAudit(
            eligible_start=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
            source_name="oddspapi",
            bookmaker="pinnacle",
            eligible_match_count=2,
            complete_match_count=1,
            coverage_ratio=Decimal("0.5000"),
            market_sample_counts={
                "asian_handicap": 1,
                "total_goals": 1,
                "match_winner": 1,
            },
            missing_market_counts={
                "asian_handicap": 1,
                "total_goals": 1,
                "match_winner": 1,
            },
            by_league={"Premier League": 1},
            by_season={2026: 1},
        ),
    )


def _historical_odds_anchor_coverage_report() -> HistoricalOddsAnchorCoverageReport:
    return HistoricalOddsAnchorCoverageReport(
        season=2026,
        eligible_start=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
        bookmaker="pinnacle",
        anchor_labels=("24h", "12h", "6h", "3h", "1h", "close"),
        eligible_match_count=12,
        market_reports={
            "asian_handicap": MarketAnchorCoverageReport(
                market_type="asian_handicap",
                eligible_match_count=12,
                sample_count=10,
                sample_coverage_ratio=Decimal("0.8333"),
                complete_core_anchor_sample_count=8,
                complete_core_anchor_coverage_ratio=Decimal("0.6667"),
                average_snapshot_count=Decimal("42.00"),
                anchor_reports={
                    "24h": AnchorCoverage(
                        label="24h",
                        sample_count=8,
                        coverage_ratio=Decimal("0.6667"),
                        sample_internal_coverage_ratio=Decimal("0.8000"),
                    )
                },
            )
        },
    )


def _baseline_qa_report() -> BaselineTrainingDatasetQaReport:
    return BaselineTrainingDatasetQaReport(
        csv_path="local_data/training/baseline.csv",
        row_count=1,
        column_count=42,
        empty_required_cells={},
        invalid_odds_cells={},
        invalid_probability_cells={},
        invalid_overround_cells={},
        overround_ranges={
            "asian_handicap": ("1.0200", "1.0200"),
            "total_goals": ("1.0200", "1.0200"),
            "match_winner": ("1.0400", "1.0400"),
        },
        by_season={"2026": 1},
        by_month={"2026-05": 1},
        league_counts={"Premier League": 1},
        low_sample_leagues={"Premier League": 1},
        match_result_counts={"home_win": 1},
        result_label_counts={},
        asian_handicap_line_counts={"-0.25": 1},
        total_goals_line_counts={"2.50": 1},
        thin_history_count=0,
        thin_history_ratio="0.0000",
        snapshot_count_ranges={
            "asian_handicap_snapshot_count": (40, 40),
            "total_goals_snapshot_count": (40, 40),
            "match_winner_snapshot_count": (40, 40),
        },
    )


def _baseline_market_report() -> BaselineTrainingDatasetMarketBaselineReport:
    return BaselineTrainingDatasetMarketBaselineReport(
        csv_path="local_data/training/baseline.csv",
        row_count=1,
        total_market_samples=3,
        total_evaluated_market_samples=3,
        total_skipped_market_samples=0,
        market_reports={
            "match_winner": MarketBaselineReport(
                market_type="match_winner",
                feature_count=1,
                evaluated_count=1,
                skipped_count=0,
                average_log_loss=Decimal("0.7000"),
                average_brier_score=Decimal("0.3000"),
                accuracy=Decimal("1.0000"),
                average_overround=Decimal("1.0400"),
                flat_bet_count=1,
                flat_bet_profit_units=Decimal("1.0000"),
                flat_bet_roi=Decimal("1.0000"),
                predicted_side_counts={"home": 1},
            )
        },
    )


def _baseline_feature_set() -> BaselineFeatureSet:
    return BaselineFeatureSet(
        rows=[
            {"match_id": "1", "split": "train"},
            {"match_id": "2", "split": "train"},
            {"match_id": "3", "split": "train"},
            {"match_id": "4", "split": "validation"},
        ],
        report=BaselineFeatureSetReport(
            csv_path="local_data/training/baseline.csv",
            row_count=4,
            train_rows=3,
            validation_rows=1,
            validation_ratio=Decimal("0.2500"),
            train_start="2026-01-20T20:00:00",
            train_end="2026-02-03T20:00:00",
            validation_start="2026-02-10T20:00:00",
            validation_end="2026-02-10T20:00:00",
            by_league={"Premier League": {"rows": 4, "train": 3, "validation": 1}},
            zero_history_rows=2,
        ),
    )


def _baseline_match_winner_model_report() -> BaselineMatchWinnerModelReport:
    return BaselineMatchWinnerModelReport(
        csv_path="local_data/training/features.csv",
        row_count=10,
        train_rows=8,
        validation_rows=2,
        close_market_reference=CloseMarketMatchWinnerReference(
            evaluated_rows=2,
            accuracy=Decimal("0.5000"),
            log_loss=Decimal("1.1000"),
            brier_score=Decimal("0.6000"),
            predicted_result_counts={"home_win": 1, "away_win": 1},
            calibration_bins=[
                CalibrationBucket(
                    bucket="0.40-0.50",
                    sample_count=2,
                    average_confidence=Decimal("0.4500"),
                    accuracy=Decimal("0.5000"),
                )
            ],
        ),
        model_reports={
            "team_form_only": MatchWinnerModelEvaluation(
                name="team_form_only",
                model_name="LogisticRegression",
                feature_count=20,
                train_rows=8,
                validation_rows=2,
                accuracy=Decimal("0.5000"),
                log_loss=Decimal("1.0000"),
                brier_score=Decimal("0.6000"),
                predicted_result_counts={"home_win": 1, "draw": 1},
                calibration_bins=[
                    CalibrationBucket(
                        bucket="0.40-0.50",
                        sample_count=2,
                        average_confidence=Decimal("0.4500"),
                        accuracy=Decimal("0.5000"),
                    )
                ],
            ),
            "team_form_plus_all_markets": MatchWinnerModelEvaluation(
                name="team_form_plus_all_markets",
                model_name="LogisticRegression",
                feature_count=32,
                train_rows=8,
                validation_rows=2,
                accuracy=Decimal("0.5000"),
                log_loss=Decimal("1.0500"),
                brier_score=Decimal("0.6100"),
                predicted_result_counts={"home_win": 1, "away_win": 1},
                calibration_bins=[
                    CalibrationBucket(
                        bucket="0.40-0.50",
                        sample_count=2,
                        average_confidence=Decimal("0.4500"),
                        accuracy=Decimal("0.5000"),
                    )
                ],
            )
        },
    )


def _baseline_asian_handicap_model_report() -> BaselineAsianHandicapModelReport:
    return BaselineAsianHandicapModelReport(
        csv_path="local_data/training/features.csv",
        row_count=10,
        train_rows=8,
        validation_rows=2,
        skipped_rows=1,
        close_market_reference=CloseMarketAsianHandicapReference(
            evaluated_rows=2,
            accuracy=Decimal("0.5000"),
            log_loss=Decimal("0.7000"),
            brier_score=Decimal("0.5000"),
            predicted_side_counts={"home_cover": 1, "away_cover": 1},
            calibration_bins=[
                CalibrationBucket(
                    bucket="0.40-0.50",
                    sample_count=2,
                    average_confidence=Decimal("0.4500"),
                    accuracy=Decimal("0.5000"),
                )
            ],
        ),
        model_reports={
            "team_form_plus_all_markets": AsianHandicapModelEvaluation(
                name="team_form_plus_all_markets",
                model_name="LogisticRegression",
                feature_count=32,
                train_rows=8,
                validation_rows=2,
                accuracy=Decimal("0.5000"),
                log_loss=Decimal("0.7000"),
                brier_score=Decimal("0.5000"),
                predicted_side_counts={"home_cover": 1, "away_cover": 1},
                calibration_bins=[
                    CalibrationBucket(
                        bucket="0.40-0.50",
                        sample_count=2,
                        average_confidence=Decimal("0.4500"),
                        accuracy=Decimal("0.5000"),
                    )
                ],
            )
        },
    )


def _baseline_total_goals_model_report() -> BaselineTotalGoalsModelReport:
    return BaselineTotalGoalsModelReport(
        csv_path="local_data/training/features.csv",
        row_count=10,
        train_rows=8,
        validation_rows=2,
        skipped_rows=1,
        close_market_reference=CloseMarketTotalGoalsReference(
            evaluated_rows=2,
            accuracy=Decimal("0.5000"),
            log_loss=Decimal("0.7000"),
            brier_score=Decimal("0.5000"),
            predicted_side_counts={"over": 1, "under": 1},
            calibration_bins=[
                CalibrationBucket(
                    bucket="0.40-0.50",
                    sample_count=2,
                    average_confidence=Decimal("0.4500"),
                    accuracy=Decimal("0.5000"),
                )
            ],
        ),
        model_reports={
            "team_form_plus_all_markets": TotalGoalsModelEvaluation(
                name="team_form_plus_all_markets",
                model_name="LogisticRegression",
                feature_count=32,
                train_rows=8,
                validation_rows=2,
                accuracy=Decimal("0.5000"),
                log_loss=Decimal("0.7000"),
                brier_score=Decimal("0.5000"),
                predicted_side_counts={"over": 1, "under": 1},
                calibration_bins=[
                    CalibrationBucket(
                        bucket="0.40-0.50",
                        sample_count=2,
                        average_confidence=Decimal("0.4500"),
                        accuracy=Decimal("0.5000"),
                    )
                ],
            )
        },
    )


def _baseline_market_diagnostics_report() -> BaselineMarketDiagnosticsReport:
    return BaselineMarketDiagnosticsReport(
        csv_path="local_data/training/features.csv",
        row_count=20,
        validation_rows=12,
        market_reports={
            "asian_handicap": MarketDiagnostics(
                market_name="asian_handicap",
                eligible_rows=10,
                skipped_rows=2,
                overall=SegmentDiagnostics(
                    segment="overall",
                    rows=10,
                    accuracy="0.6000",
                    actual_counts={"home_cover": 6, "away_cover": 4},
                    predicted_counts={"home_cover": 5, "away_cover": 5},
                ),
                actual_side_counts={"home_cover": 6, "away_cover": 4},
                predicted_side_counts={"home_cover": 5, "away_cover": 5},
                by_league=[],
                by_line=[],
                by_market_confidence=[],
                by_actual_side=[],
            ),
            "total_goals": MarketDiagnostics(
                market_name="total_goals",
                eligible_rows=8,
                skipped_rows=4,
                overall=SegmentDiagnostics(
                    segment="overall",
                    rows=8,
                    accuracy="0.5000",
                    actual_counts={"over": 4, "under": 4},
                    predicted_counts={"over": 3, "under": 5},
                ),
                actual_side_counts={"over": 4, "under": 4},
                predicted_side_counts={"over": 3, "under": 5},
                by_league=[],
                by_line=[],
                by_market_confidence=[],
                by_actual_side=[],
            ),
        },
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

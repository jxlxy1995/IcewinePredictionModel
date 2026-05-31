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
from icewine_prediction.baseline_dynamic_feature_set_service import (
    BaselineDynamicFeatureSet,
    BaselineDynamicFeatureSetReport,
)
from icewine_prediction.baseline_edge_backtest_service import (
    BaselineEdgeBacktestReport,
    EdgeMarketBacktest,
    EdgeModelBacktest,
    EdgeThresholdBucket,
)
from icewine_prediction.baseline_walk_forward_edge_service import (
    BaselineWalkForwardEdgeReport,
    WalkForwardFoldBacktest,
    WalkForwardMarketBacktest,
    WalkForwardModelBacktest,
    WalkForwardThresholdSummary,
)
from icewine_prediction.baseline_recommendation_sandbox_service import (
    BaselineRecommendationSandboxReport,
    SandboxCandidate,
    SandboxGroupSummary,
)
from icewine_prediction.baseline_walk_forward_sandbox_service import (
    BaselineWalkForwardSandboxReport,
    WalkForwardSandboxFoldReport,
    WalkForwardSandboxSideSummary,
)
from icewine_prediction.baseline_away_cover_stability_service import (
    AwayCoverStabilitySummary,
    AwayCoverThresholdSummary,
    BaselineAwayCoverStabilityReport,
)
from icewine_prediction.baseline_away_cover_bucket_threshold_service import (
    BaselineAwayCoverBucketThresholdReport,
    BucketThresholdSelection,
)
from icewine_prediction.baseline_away_cover_bucket_sandbox_service import (
    BaselineAwayCoverBucketSandboxReport,
    BucketSandboxStrategySummary,
)
from icewine_prediction.baseline_total_goals_edge_stability_service import (
    BaselineTotalGoalsEdgeStabilityReport,
    TotalGoalsStabilitySummary,
    TotalGoalsThresholdSummary,
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


def test_samples_group_exposes_baseline_dynamic_feature_set_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-dynamic-feature-set" in result.stdout


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


def test_samples_group_exposes_baseline_edge_backtest_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-edge-backtest" in result.stdout


def test_samples_group_exposes_baseline_walk_forward_edge_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-walk-forward-edge" in result.stdout


def test_samples_group_exposes_baseline_recommendation_sandbox_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-recommendation-sandbox" in result.stdout


def test_samples_group_exposes_baseline_walk_forward_sandbox_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-walk-forward-sandbox" in result.stdout


def test_samples_group_exposes_baseline_away_cover_stability_help():
    runner = CliRunner()

    result = runner.invoke(app, ["samples", "--help"])

    assert result.exit_code == 0
    assert "baseline-away-cover-stability" in result.stdout


def test_format_baseline_training_dataset_command_result_summarizes_outputs():
    text = format_baseline_training_dataset_command_result(
        dataset_path="local_data/training/baseline.csv",
        report_path="docs/数据审计/baseline.md",
        dataset=_baseline_dataset(),
    )

    assert "baseline dataset written" in text
    assert "local_data/training/baseline.csv" in text
    assert "docs/数据审计/baseline.md" in text
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
            "docs/数据审计/test.md",
            "--eligible-start",
            "2026-01-15",
        ],
    )

    assert result.exit_code == 0
    assert captured["source_name"] == "oddspapi"
    assert captured["bookmaker"] == "pinnacle"
    assert captured["eligible_start"].strftime("%Y-%m-%d %H:%M") == "2026-01-15 00:00"
    assert captured["dataset_path"].endswith("local_data\\training\\test.csv")
    assert captured["report_path"].endswith("docs\\数据审计\\test.md")
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
            "docs/数据审计/baseline-qa.md",
            "--low-sample-threshold",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("docs\\数据审计\\baseline-qa.md")
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
            "docs/模型实验/market-baseline.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("docs\\模型实验\\market-baseline.md")
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
            "docs/数据审计/anchor.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["season"] == 2026
    assert captured["bookmaker"] == "pinnacle"
    assert captured["eligible_start"].strftime("%Y-%m-%d") == "2026-01-15"
    assert captured["output_path"].endswith("docs\\数据审计\\anchor.md")
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
            "docs/数据审计/features.md",
            "--validation-ratio",
            "0.25",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\baseline.csv")
    assert captured["output_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\数据审计\\features.md")
    assert captured["validation_ratio"] == "0.25"
    assert "baseline feature set written" in result.stdout
    assert "rows 4 train 3 validation 1" in result.stdout


def test_samples_baseline_dynamic_feature_set_command_writes_csv_and_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(session, csv_path, *, bookmaker):
        captured["csv_path"] = str(csv_path)
        captured["bookmaker"] = bookmaker
        return _baseline_dynamic_feature_set()

    def fake_write_csv(feature_set, output_path):
        captured["output_path"] = str(output_path)

    def fake_write_report(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr("icewine_prediction.cli.build_baseline_dynamic_feature_set", fake_build)
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_dynamic_feature_set_csv",
        fake_write_csv,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_dynamic_feature_set_report",
        fake_write_report,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-dynamic-feature-set",
            "--csv-path",
            "local_data/training/features.csv",
            "--output-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/数据审计/dynamic.md",
            "--bookmaker",
            "pinnacle",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["output_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\数据审计\\dynamic.md")
    assert captured["bookmaker"] == "pinnacle"
    assert "baseline dynamic feature set written" in result.stdout
    assert "rows 4 asian 4 total 4 complete-core 4" in result.stdout


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
            "docs/模型实验/match-winner.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\match-winner.md")
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
            "docs/模型实验/asian-handicap.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\asian-handicap.md")
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
            "docs/模型实验/total-goals.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\total-goals.md")
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
            "docs/数据审计/diagnostics.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\features.csv")
    assert captured["report_path"].endswith("docs\\数据审计\\diagnostics.md")
    assert "baseline market diagnostics written" in result.stdout
    assert "asian_handicap accuracy 0.6000 rows 10" in result.stdout
    assert "total_goals accuracy 0.5000 rows 8" in result.stdout


def test_samples_baseline_edge_backtest_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, thresholds):
        captured["csv_path"] = str(csv_path)
        captured["thresholds"] = thresholds
        return _baseline_edge_backtest_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_edge_backtest_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_edge_backtest_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-edge-backtest",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/模型实验/edge.md",
            "--thresholds",
            "0.00,0.05",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\edge.md")
    assert captured["thresholds"] == ("0.00", "0.05")
    assert "baseline edge backtest written" in result.stdout
    assert "asian_handicap calibrated_hgb_team_form_plus_all_markets bets 2 roi 0.1000" in result.stdout


def test_samples_baseline_walk_forward_edge_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, thresholds, train_ratio, validation_ratio, fold_count):
        captured["csv_path"] = str(csv_path)
        captured["thresholds"] = thresholds
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        return _baseline_walk_forward_edge_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_walk_forward_edge_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_walk_forward_edge_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-walk-forward-edge",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/模型实验/walk-forward.md",
            "--thresholds",
            "0.00,0.05",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\walk-forward.md")
    assert captured["thresholds"] == ("0.00", "0.05")
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert "baseline walk-forward edge backtest written" in result.stdout
    assert "asian_handicap raw_hgb_team_form_plus_all_markets threshold 0.0000 positive 1/2" in result.stdout


def test_samples_baseline_recommendation_sandbox_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, edge_threshold, top_n):
        captured["csv_path"] = str(csv_path)
        captured["edge_threshold"] = edge_threshold
        captured["top_n"] = top_n
        return _baseline_recommendation_sandbox_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_recommendation_sandbox_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_recommendation_sandbox_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-recommendation-sandbox",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/妯″瀷瀹為獙/recommendation-sandbox.md",
            "--edge-threshold",
            "0.10",
            "--top-n",
            "20",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\妯″瀷瀹為獙\\recommendation-sandbox.md")
    assert captured["edge_threshold"] == "0.10"
    assert captured["top_n"] == 20
    assert "baseline recommendation sandbox written" in result.stdout
    assert "asian_handicap raw_hgb_team_form_plus_all_markets candidates 2 displayed 1" in result.stdout


def test_samples_baseline_walk_forward_sandbox_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(
        csv_path,
        *,
        edge_threshold,
        train_ratio,
        validation_ratio,
        fold_count,
        top_n_per_fold,
    ):
        captured["csv_path"] = str(csv_path)
        captured["edge_threshold"] = edge_threshold
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        captured["top_n_per_fold"] = top_n_per_fold
        return _baseline_walk_forward_sandbox_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_walk_forward_sandbox_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_walk_forward_sandbox_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-walk-forward-sandbox",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/妯″瀷瀹為獙/walk-forward-sandbox.md",
            "--edge-threshold",
            "0.10",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
            "--top-n-per-fold",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\妯″瀷瀹為獙\\walk-forward-sandbox.md")
    assert captured["edge_threshold"] == "0.10"
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert captured["top_n_per_fold"] == 5
    assert "baseline walk-forward recommendation sandbox written" in result.stdout
    assert "asian_handicap raw_hgb_team_form_plus_all_markets folds 2 candidates 4 positive 1/2" in result.stdout


def test_samples_baseline_away_cover_stability_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, thresholds, train_ratio, validation_ratio, fold_count):
        captured["csv_path"] = str(csv_path)
        captured["thresholds"] = thresholds
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        return _baseline_away_cover_stability_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_away_cover_stability_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_away_cover_stability_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-away-cover-stability",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/妯″瀷瀹為獙/away-cover-stability.md",
            "--thresholds",
            "0.08,0.10",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\妯″瀷瀹為獙\\away-cover-stability.md")
    assert captured["thresholds"] == ("0.08", "0.10")
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert "baseline away-cover stability written" in result.stdout
    assert "asian_handicap raw_hgb_team_form_plus_all_markets away_cover thresholds 2" in result.stdout


def test_samples_baseline_away_cover_bucket_threshold_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, thresholds, train_ratio, validation_ratio, fold_count):
        captured["csv_path"] = str(csv_path)
        captured["thresholds"] = thresholds
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        return _baseline_away_cover_bucket_threshold_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_away_cover_bucket_threshold_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_away_cover_bucket_threshold_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-away-cover-bucket-threshold",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/模型实验/away-cover-bucket.md",
            "--thresholds",
            "0.08,0.10",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\away-cover-bucket.md")
    assert captured["thresholds"] == ("0.08", "0.10")
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert "baseline away-cover bucket threshold written" in result.stdout
    assert "asian_handicap raw_hgb_team_form_plus_all_markets away_cover buckets 1" in result.stdout


def test_samples_baseline_away_cover_bucket_sandbox_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(
        csv_path,
        *,
        v1_edge_threshold,
        bucket_thresholds,
        train_ratio,
        validation_ratio,
        fold_count,
    ):
        captured["csv_path"] = str(csv_path)
        captured["v1_edge_threshold"] = v1_edge_threshold
        captured["bucket_thresholds"] = bucket_thresholds
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        return _baseline_away_cover_bucket_sandbox_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_away_cover_bucket_sandbox_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_away_cover_bucket_sandbox_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-away-cover-bucket-sandbox",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/模型实验/away-cover-bucket-sandbox.md",
            "--v1-edge-threshold",
            "0.10",
            "--away-underdog-threshold",
            "0.20",
            "--pickem-threshold",
            "0.08",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\模型实验\\away-cover-bucket-sandbox.md")
    assert captured["v1_edge_threshold"] == "0.10"
    assert captured["bucket_thresholds"] == {
        "away_underdog": "0.20",
        "pickem": "0.08",
    }
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert "baseline away-cover bucket sandbox written" in result.stdout
    assert "asian_away_cover_hgb_bucket_v2 bets 4 positive 2/2 roi 0.1000" in result.stdout


def test_samples_baseline_total_goals_edge_stability_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(csv_path, *, thresholds, train_ratio, validation_ratio, fold_count):
        captured["csv_path"] = str(csv_path)
        captured["thresholds"] = thresholds
        captured["train_ratio"] = train_ratio
        captured["validation_ratio"] = validation_ratio
        captured["fold_count"] = fold_count
        return _baseline_total_goals_edge_stability_report()

    def fake_write(report, report_path):
        captured["report_path"] = str(report_path)

    monkeypatch.setattr(
        "icewine_prediction.cli.build_baseline_total_goals_edge_stability_report",
        fake_build,
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.write_baseline_total_goals_edge_stability_report",
        fake_write,
    )

    result = runner.invoke(
        app,
        [
            "samples",
            "baseline-total-goals-edge-stability",
            "--csv-path",
            "local_data/training/dynamic.csv",
            "--report-path",
            "docs/妯″瀷瀹為獙/total-goals-edge.md",
            "--thresholds",
            "0.08,0.10",
            "--train-ratio",
            "0.50",
            "--validation-ratio",
            "0.20",
            "--fold-count",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert captured["csv_path"].endswith("local_data\\training\\dynamic.csv")
    assert captured["report_path"].endswith("docs\\妯″瀷瀹為獙\\total-goals-edge.md")
    assert captured["thresholds"] == ("0.08", "0.10")
    assert captured["train_ratio"] == "0.50"
    assert captured["validation_ratio"] == "0.20"
    assert captured["fold_count"] == 3
    assert "baseline total-goals edge stability written" in result.stdout
    assert "total_goals raw_hgb_team_form_plus_all_markets thresholds 1" in result.stdout


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


def _baseline_dynamic_feature_set() -> BaselineDynamicFeatureSet:
    return BaselineDynamicFeatureSet(
        rows=[{"match_id": "1", "asian_handicap_6h_line": "-0.50"}],
        fieldnames=("match_id", "asian_handicap_6h_line"),
        report=BaselineDynamicFeatureSetReport(
            source_csv_path="local_data/training/features.csv",
            row_count=4,
            rows_with_asian_handicap_dynamic=4,
            rows_with_total_goals_dynamic=4,
            complete_core_anchor_rows=4,
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


def _baseline_edge_backtest_report() -> BaselineEdgeBacktestReport:
    bucket = EdgeThresholdBucket(
        threshold=Decimal("0.0000"),
        bet_count=2,
        accuracy=Decimal("0.5000"),
        profit=Decimal("0.2000"),
        roi=Decimal("0.1000"),
    )
    model = EdgeModelBacktest(
        name="calibrated_hgb_team_form_plus_all_markets",
        estimator_name="HistGradientBoostingClassifier",
        calibration_method="sigmoid",
        feature_count=32,
        train_rows=8,
        validation_rows=2,
        accuracy=Decimal("0.5000"),
        log_loss=Decimal("0.7000"),
        brier_score=Decimal("0.5000"),
        threshold_buckets=[bucket],
    )
    return BaselineEdgeBacktestReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        thresholds=(Decimal("0.0000"),),
        market_reports={
            "asian_handicap": EdgeMarketBacktest(
                market_type="asian_handicap",
                train_rows=8,
                validation_rows=2,
                skipped_rows=0,
                model_reports={model.name: model},
            )
        },
    )


def _baseline_walk_forward_edge_report() -> BaselineWalkForwardEdgeReport:
    bucket = EdgeThresholdBucket(
        threshold=Decimal("0.0000"),
        bet_count=2,
        accuracy=Decimal("0.5000"),
        profit=Decimal("0.2000"),
        roi=Decimal("0.1000"),
    )
    edge_model = EdgeModelBacktest(
        name="raw_hgb_team_form_plus_all_markets",
        estimator_name="HistGradientBoostingClassifier",
        calibration_method="none",
        feature_count=32,
        train_rows=8,
        validation_rows=2,
        accuracy=Decimal("0.5000"),
        log_loss=Decimal("0.7000"),
        brier_score=Decimal("0.5000"),
        threshold_buckets=[bucket],
    )
    model = WalkForwardModelBacktest(
        name="raw_hgb_team_form_plus_all_markets",
        threshold_summaries=[
            WalkForwardThresholdSummary(
                threshold=Decimal("0.0000"),
                fold_count=2,
                total_bets=4,
                positive_roi_folds=1,
                average_roi=Decimal("0.0500"),
                worst_roi=Decimal("-0.0500"),
            )
        ],
        fold_reports=[
            WalkForwardFoldBacktest(
                fold_index=1,
                train_rows=8,
                validation_rows=2,
                model_report=edge_model,
            )
        ],
    )
    return BaselineWalkForwardEdgeReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        thresholds=(Decimal("0.0000"),),
        market_reports={
            "asian_handicap": WalkForwardMarketBacktest(
                market_type="asian_handicap",
                model_reports={model.name: model},
            )
        },
    )


def _baseline_recommendation_sandbox_report() -> BaselineRecommendationSandboxReport:
    candidate = SandboxCandidate(
        match_id="1",
        kickoff_time="2026-05-20T20:00:00",
        league_name="Premier League",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        market_type="asian_handicap",
        line=Decimal("-0.2500"),
        side="home_cover",
        odds=Decimal("1.9000"),
        model_probability=Decimal("0.6200"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1200"),
        actual_side="home_cover",
        profit=Decimal("0.9000"),
    )
    return BaselineRecommendationSandboxReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        train_rows=8,
        validation_rows=2,
        skipped_rows=0,
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        edge_threshold=Decimal("0.1000"),
        top_n=1,
        total_candidates=2,
        total_profit=Decimal("-0.1000"),
        roi=Decimal("-0.0500"),
        displayed_candidates=[candidate],
        candidates=[candidate],
        side_summaries=[
            SandboxGroupSummary(
                name="home_cover",
                candidate_count=2,
                wins=1,
                profit=Decimal("-0.1000"),
                roi=Decimal("-0.0500"),
            )
        ],
        league_summaries=[
            SandboxGroupSummary(
                name="Premier League",
                candidate_count=2,
                wins=1,
                profit=Decimal("-0.1000"),
                roi=Decimal("-0.0500"),
            )
        ],
    )


def _baseline_walk_forward_sandbox_report() -> BaselineWalkForwardSandboxReport:
    candidate = SandboxCandidate(
        match_id="1",
        kickoff_time="2026-05-20T20:00:00",
        league_name="Premier League",
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        market_type="asian_handicap",
        line=Decimal("-0.2500"),
        side="away_cover",
        odds=Decimal("1.9000"),
        model_probability=Decimal("0.6200"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1200"),
        actual_side="away_cover",
        profit=Decimal("0.9000"),
    )
    side_summary = SandboxGroupSummary(
        name="away_cover",
        candidate_count=2,
        wins=1,
        profit=Decimal("-0.1000"),
        roi=Decimal("-0.0500"),
    )
    return BaselineWalkForwardSandboxReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        edge_threshold=Decimal("0.1000"),
        top_n_per_fold=1,
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        total_candidates=4,
        total_profit=Decimal("0.2000"),
        roi=Decimal("0.0500"),
        positive_roi_folds=1,
        fold_reports=[
            WalkForwardSandboxFoldReport(
                fold_index=1,
                train_rows=8,
                validation_rows=2,
                candidate_count=2,
                profit=Decimal("0.2000"),
                roi=Decimal("0.1000"),
                positive_roi=True,
                side_summaries=[side_summary],
                displayed_candidates=[candidate],
            )
        ],
        side_summaries=[
            WalkForwardSandboxSideSummary(
                name="away_cover",
                candidate_count=4,
                positive_roi_folds=1,
                profit=Decimal("0.2000"),
                roi=Decimal("0.0500"),
            )
        ],
    )


def _baseline_away_cover_stability_report() -> BaselineAwayCoverStabilityReport:
    return BaselineAwayCoverStabilityReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        thresholds=(Decimal("0.0800"), Decimal("0.1000")),
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        side="away_cover",
        threshold_summaries=[
            AwayCoverThresholdSummary(
                threshold=Decimal("0.0800"),
                candidate_count=5,
                positive_roi_folds=2,
                profit=Decimal("0.5000"),
                roi=Decimal("0.1000"),
                worst_fold_roi=Decimal("0.0500"),
            ),
            AwayCoverThresholdSummary(
                threshold=Decimal("0.1000"),
                candidate_count=4,
                positive_roi_folds=2,
                profit=Decimal("0.4000"),
                roi=Decimal("0.1000"),
                worst_fold_roi=Decimal("0.0500"),
            )
        ],
        league_summaries=[
            AwayCoverStabilitySummary(
                name="Premier League",
                candidate_count=4,
                positive_roi_folds=2,
                profit=Decimal("0.4000"),
                roi=Decimal("0.1000"),
                worst_fold_roi=Decimal("0.0500"),
            )
        ],
        line_bucket_summaries=[
            AwayCoverStabilitySummary(
                name="away_underdog",
                candidate_count=4,
                positive_roi_folds=2,
                profit=Decimal("0.4000"),
                roi=Decimal("0.1000"),
                worst_fold_roi=Decimal("0.0500"),
            )
        ],
    )


def _baseline_away_cover_bucket_threshold_report() -> BaselineAwayCoverBucketThresholdReport:
    selection = BucketThresholdSelection(
        line_bucket="away_underdog",
        threshold=Decimal("0.1000"),
        candidate_count=4,
        positive_roi_folds=2,
        profit=Decimal("0.4000"),
        roi=Decimal("0.1000"),
        worst_fold_roi=Decimal("0.0500"),
    )
    return BaselineAwayCoverBucketThresholdReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        thresholds=(Decimal("0.0800"), Decimal("0.1000")),
        strategy_key="asian_away_cover_hgb_bucket_v2",
        strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        side="away_cover",
        selected_thresholds=[selection],
        bucket_threshold_summaries={"away_underdog": [selection]},
    )


def _baseline_away_cover_bucket_sandbox_report() -> BaselineAwayCoverBucketSandboxReport:
    return BaselineAwayCoverBucketSandboxReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        v1_edge_threshold=Decimal("0.1000"),
        bucket_thresholds={
            "away_underdog": Decimal("0.2000"),
            "pickem": Decimal("0.0800"),
        },
        market_type="asian_handicap",
        model_name="raw_hgb_team_form_plus_all_markets",
        strategy_summaries=[
            BucketSandboxStrategySummary(
                strategy_key="asian_away_cover_hgb_edge_v1",
                display_name="亚盘客队方向 · HGB边际 v1",
                candidate_count=5,
                positive_roi_folds=1,
                profit=Decimal("0.2500"),
                roi=Decimal("0.0500"),
                bucket_thresholds={"all": Decimal("0.1000")},
            ),
            BucketSandboxStrategySummary(
                strategy_key="asian_away_cover_hgb_bucket_v2",
                display_name="亚盘客队方向 · HGB分盘口桶 v2",
                candidate_count=4,
                positive_roi_folds=2,
                profit=Decimal("0.4000"),
                roi=Decimal("0.1000"),
                bucket_thresholds={
                    "away_underdog": Decimal("0.2000"),
                    "pickem": Decimal("0.0800"),
                },
            ),
        ],
        fold_reports=[],
        bucket_summaries=[],
    )


def _baseline_total_goals_edge_stability_report() -> BaselineTotalGoalsEdgeStabilityReport:
    threshold = TotalGoalsThresholdSummary(
        threshold=Decimal("0.1000"),
        candidate_count=4,
        positive_roi_folds=2,
        profit=Decimal("0.4000"),
        roi=Decimal("0.1000"),
        worst_fold_roi=Decimal("0.0500"),
    )
    return BaselineTotalGoalsEdgeStabilityReport(
        csv_path="local_data/training/dynamic.csv",
        row_count=10,
        fold_count=2,
        train_ratio=Decimal("0.5000"),
        validation_ratio=Decimal("0.2000"),
        thresholds=(Decimal("0.1000"),),
        market_type="total_goals",
        model_name="raw_hgb_team_form_plus_all_markets",
        threshold_summaries=[threshold],
        side_summaries=[
            TotalGoalsStabilitySummary(
                name="over",
                candidate_count=4,
                positive_roi_folds=2,
                profit=Decimal("0.4000"),
                roi=Decimal("0.1000"),
                worst_fold_roi=Decimal("0.0500"),
            )
        ],
        league_summaries=[],
        line_bucket_summaries=[],
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

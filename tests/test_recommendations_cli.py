from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from icewine_prediction.cli import app, format_recommendation_line
from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.paper_recommendation_queue_service import (
    PaperRecommendationQueueReport,
)
from icewine_prediction.recommendation_service import Recommendation


def test_recommendations_group_exposes_preview_help():
    runner = CliRunner()

    result = runner.invoke(app, ["recommendations", "--help"])

    assert result.exit_code == 0
    assert "preview" in result.stdout
    assert "paper-queue" in result.stdout


def test_recommendations_paper_queue_command_writes_report(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_build(
        session,
        *,
        now,
        hours,
        near_start_hours,
        edge_threshold,
        prefetch_odds,
        odds_prefetcher,
        display_name_service,
    ):
        captured["hours"] = hours
        captured["near_start_hours"] = near_start_hours
        captured["edge_threshold"] = edge_threshold
        captured["prefetch_odds"] = prefetch_odds
        captured["has_prefetcher"] = odds_prefetcher is not None
        captured["display_name_service"] = display_name_service
        return PaperRecommendationQueueReport(
            generated_at="2026-05-30T00:00:00+08:00",
            window_start="2026-05-30T00:00:00+08:00",
            window_end="2026-06-02T00:00:00+08:00",
            hours=72,
            near_start_hours=6,
            edge_threshold=Decimal("0.1000"),
            model_name="raw_hgb_team_form_plus_all_markets",
            total_matches=3,
            candidate_count=1,
            status_counts={"candidate": 1, "no_odds": 2},
            prefetch_requested=True,
            near_start_fixture_ids=["1001"],
            prefetch_result={"created": 2, "skipped": 0, "failed_fixture_id": None, "error_message": None},
            rows=[],
        )

    def fake_write(report, output_path):
        captured["report_path"] = str(output_path)

    monkeypatch.setattr("icewine_prediction.cli.build_paper_recommendation_queue", fake_build)
    monkeypatch.setattr("icewine_prediction.cli.write_paper_recommendation_queue_report", fake_write)

    result = runner.invoke(
        app,
        [
            "recommendations",
            "paper-queue",
            "--hours",
            "72",
            "--near-start-hours",
            "6",
            "--edge-threshold",
            "0.10",
            "--prefetch-odds",
            "--report-path",
            "docs/模型实验/paper-queue.md",
        ],
    )

    assert result.exit_code == 0
    assert captured["hours"] == 72
    assert captured["near_start_hours"] == 6
    assert captured["edge_threshold"] == "0.10"
    assert captured["prefetch_odds"] is True
    assert captured["has_prefetcher"] is True
    assert isinstance(captured["display_name_service"], DisplayNameService)
    assert captured["report_path"].endswith("docs\\模型实验\\paper-queue.md")
    assert "paper recommendation queue written" in result.stdout
    assert "candidates 1/3" in result.stdout


def test_recommendations_paper_replay_command_records_and_settles(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_latest_feature_path(session):
        captured["feature_session"] = session
        return "local_data/training/latest.csv"

    def fake_scorer_factory(path):
        captured["feature_path"] = str(path)
        return "scorer-factory"

    def fake_replay(
        session,
        *,
        from_time,
        to_time,
        scorer_factory,
        recorded_at,
        edge_threshold,
        settle,
        display_name_service,
    ):
        captured["from_time"] = from_time.isoformat()
        captured["to_time"] = to_time.isoformat()
        captured["scorer_factory"] = scorer_factory
        captured["edge_threshold"] = edge_threshold
        captured["settle"] = settle
        captured["recorded_at"] = recorded_at
        captured["display_name_service"] = display_name_service
        return SimpleNamespace(
            scanned_matches=8,
            candidate_rows=3,
            created_records=2,
            duplicate_records=1,
            settled_records=2,
            skipped_settlement_records=0,
            unsettleable_records=0,
        )

    monkeypatch.setattr("icewine_prediction.cli._latest_successful_dynamic_feature_path", fake_latest_feature_path)
    monkeypatch.setattr("icewine_prediction.cli.build_walk_forward_replay_scorer_factory", fake_scorer_factory)
    monkeypatch.setattr("icewine_prediction.cli.replay_finished_matches_as_paper_recommendations", fake_replay)

    result = runner.invoke(
        app,
        [
            "recommendations",
            "paper-replay",
            "--from-time",
            "2026-05-30T00:00:00+08:00",
            "--to-time",
            "2026-05-31T00:00:00+08:00",
            "--edge-threshold",
            "0.10",
            "--settle",
        ],
    )

    assert result.exit_code == 0
    assert captured["from_time"] == "2026-05-30T00:00:00+08:00"
    assert captured["to_time"] == "2026-05-31T00:00:00+08:00"
    assert captured["feature_path"] == "local_data\\training\\latest.csv"
    assert captured["scorer_factory"] == "scorer-factory"
    assert captured["edge_threshold"] == "0.10"
    assert captured["settle"] is True
    assert isinstance(captured["display_name_service"], DisplayNameService)
    assert "paper replay scanned 8 matches" in result.stdout
    assert "created 2" in result.stdout
    assert "settled 2" in result.stdout


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
            historical_sample_count=12,
            historical_roi=Decimal("0.0833"),
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
    assert "历史 12场" in line
    assert "ROI 0.0833" in line
    assert "期望进球 1.80-1.00" in line

    assert "意甲 2026-05-24 00:00 博洛尼亚 vs 国际米兰" in line
    assert "亚盘 主队 B 1.25手" in line
    assert "大小球 观望 D 0手" in line
    assert "weak_market_signal" in line

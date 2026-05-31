from decimal import Decimal

from icewine_prediction.baseline_total_goals_edge_stability_service import (
    _total_line_bucket,
    build_baseline_total_goals_edge_stability_report,
    format_baseline_total_goals_edge_stability_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate


def test_build_baseline_total_goals_edge_stability_report_summarizes_thresholds(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_total_goals_feature_csv(), encoding="utf-8")

    report = build_baseline_total_goals_edge_stability_report(
        csv_path,
        thresholds=("0.00", "0.10"),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
    )

    assert report.row_count == 64
    assert report.fold_count == 3
    assert report.market_type == "total_goals"
    assert report.threshold_summaries[0].threshold == Decimal("0.0000")
    assert report.threshold_summaries[0].candidate_count > 0
    assert report.side_summaries
    assert {summary.name for summary in report.side_summaries} <= {"over", "under"}
    assert report.line_bucket_summaries


def test_format_baseline_total_goals_edge_stability_report_includes_core_tables(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_total_goals_feature_csv(), encoding="utf-8")

    report = build_baseline_total_goals_edge_stability_report(
        csv_path,
        thresholds=("0.00",),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_total_goals_edge_stability_report(report)

    assert "# Baseline Total Goals Edge Stability v1" in text
    assert "| Threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text
    assert "| Side | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text
    assert "| Total line bucket | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text


def test_total_line_bucket_groups_common_total_lines():
    assert _total_line_bucket(_candidate_with_line(Decimal("2.00"))) == "low_<=2.25"
    assert _total_line_bucket(_candidate_with_line(Decimal("2.50"))) == "mid_2.50"
    assert _total_line_bucket(_candidate_with_line(Decimal("2.75"))) == "mid_2.75"
    assert _total_line_bucket(_candidate_with_line(Decimal("3.00"))) == "high_>=3.00"


def _candidate_with_line(line: Decimal) -> SandboxCandidate:
    return SandboxCandidate(
        match_id="1",
        kickoff_time="2026-05-30T20:00:00",
        league_name="Premier League",
        home_team_name="Home",
        away_team_name="Away",
        market_type="total_goals",
        line=line,
        side="over",
        odds=Decimal("1.900"),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1000"),
        actual_side="over",
        profit=Decimal("0.9000"),
    )


def _total_goals_feature_csv() -> str:
    headers = [
        "match_id",
        "league_name",
        "kickoff_time",
        "split",
        "home_team_name",
        "away_team_name",
        "target_total_goals_over_result",
        "target_total_goals_under_result",
        "total_goals_close_line",
        "total_goals_over_odds",
        "total_goals_under_odds",
        "home_prior_matches",
        "home_prior_points_per_match",
        "home_prior_win_rate",
        "home_prior_draw_rate",
        "home_prior_loss_rate",
        "home_prior_goals_for_per_match",
        "home_prior_goals_against_per_match",
        "home_prior_home_matches",
        "home_prior_home_points_per_match",
        "home_rest_days",
        "away_prior_matches",
        "away_prior_points_per_match",
        "away_prior_win_rate",
        "away_prior_draw_rate",
        "away_prior_loss_rate",
        "away_prior_goals_for_per_match",
        "away_prior_goals_against_per_match",
        "away_prior_away_matches",
        "away_prior_away_points_per_match",
        "away_rest_days",
        "match_winner_home_implied_probability",
        "match_winner_draw_implied_probability",
        "match_winner_away_implied_probability",
        "match_winner_overround",
        "asian_handicap_home_implied_probability",
        "asian_handicap_away_implied_probability",
        "asian_handicap_overround",
        "total_goals_over_implied_probability",
        "total_goals_under_implied_probability",
        "total_goals_overround",
    ]
    lines = [",".join(headers)]
    for index in range(1, 65):
        over_side = index % 4 != 0
        over_strength = "0.75" if over_side else "0.20"
        under_strength = "0.20" if over_side else "0.75"
        line = "2.25" if index % 4 == 0 else "2.75" if index % 5 == 0 else "2.50"
        lines.append(
            ",".join(
                [
                    str(index),
                    "Premier League" if index <= 32 else "La Liga",
                    f"2026-05-{index:02d}T20:00:00",
                    "train" if index <= 44 else "validation",
                    f"Home {index}",
                    f"Away {index}",
                    "win" if over_side else "loss",
                    "loss" if over_side else "win",
                    line,
                    "1.900",
                    "1.900",
                    "5",
                    over_strength,
                    over_strength,
                    "0.1000",
                    under_strength,
                    "1.6000",
                    "1.0000",
                    "3",
                    over_strength,
                    "7.00",
                    "5",
                    under_strength,
                    under_strength,
                    "0.1000",
                    over_strength,
                    "1.0000",
                    "1.6000",
                    "3",
                    under_strength,
                    "7.00",
                    over_strength,
                    "0.2500",
                    under_strength,
                    "1.0400",
                    "0.5000",
                    "0.5000",
                    "1.0000",
                    "0.5000",
                    "0.5000",
                    "1.0000",
                ]
            )
        )
    return "\n".join(lines) + "\n"

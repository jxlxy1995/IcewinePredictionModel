from decimal import Decimal

from icewine_prediction.baseline_away_cover_stability_service import (
    build_baseline_away_cover_stability_report,
    format_baseline_away_cover_stability_report,
)


def test_build_baseline_away_cover_stability_report_summarizes_thresholds(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")

    report = build_baseline_away_cover_stability_report(
        csv_path,
        thresholds=("0.00", "0.10"),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=3,
    )

    assert report.row_count == 60
    assert report.fold_count == 3
    assert report.threshold_summaries[0].threshold == Decimal("0.0000")
    assert report.threshold_summaries[0].candidate_count > 0
    assert report.threshold_summaries[0].positive_roi_folds >= 0
    assert report.league_summaries
    assert report.line_bucket_summaries
    assert {summary.name for summary in report.line_bucket_summaries}


def test_format_baseline_away_cover_stability_report_includes_core_tables(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_away_cover_feature_csv(), encoding="utf-8")
    report = build_baseline_away_cover_stability_report(
        csv_path,
        thresholds=("0.00",),
        train_ratio="0.50",
        validation_ratio="0.20",
        fold_count=2,
    )

    text = format_baseline_away_cover_stability_report(report)

    assert "# Baseline Away Cover Stability v1" in text
    assert "| Threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text
    assert "| League | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text
    assert "| Line bucket | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |" in text


def _away_cover_feature_csv() -> str:
    headers = [
        "match_id",
        "league_name",
        "kickoff_time",
        "split",
        "home_team_name",
        "away_team_name",
        "target_asian_handicap_home_result",
        "target_asian_handicap_away_result",
        "asian_handicap_close_line",
        "asian_handicap_home_odds",
        "asian_handicap_away_odds",
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
        "total_goals_close_line",
        "total_goals_over_implied_probability",
        "total_goals_under_implied_probability",
        "total_goals_overround",
    ]
    lines = [",".join(headers)]
    for index in range(1, 61):
        away_side = index % 4 != 0
        away_strength = "0.75" if away_side else "0.20"
        home_strength = "0.20" if away_side else "0.75"
        line = "0.50" if index % 3 == 0 else "-0.25"
        lines.append(
            ",".join(
                [
                    str(index),
                    "Premier League" if index <= 30 else "La Liga",
                    f"2026-05-{index:02d}T20:00:00",
                    "train" if index <= 42 else "validation",
                    f"Home {index}",
                    f"Away {index}",
                    "loss" if away_side else "win",
                    "win" if away_side else "loss",
                    line,
                    "1.900",
                    "1.900",
                    "5",
                    home_strength,
                    home_strength,
                    "0.1000",
                    away_strength,
                    "1.0000",
                    "1.5000",
                    "3",
                    home_strength,
                    "7.00",
                    "5",
                    away_strength,
                    away_strength,
                    "0.1000",
                    home_strength,
                    "1.5000",
                    "1.0000",
                    "3",
                    away_strength,
                    "7.00",
                    home_strength,
                    "0.2500",
                    away_strength,
                    "1.0400",
                    "0.5000",
                    "0.5000",
                    "1.0000",
                    "2.50",
                    "0.5000",
                    "0.5000",
                    "1.0000",
                ]
            )
        )
    return "\n".join(lines) + "\n"

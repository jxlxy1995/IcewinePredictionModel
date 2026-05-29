from icewine_prediction.baseline_edge_backtest_service import (
    build_baseline_edge_backtest_report,
    format_baseline_edge_backtest_report,
)


def test_build_baseline_edge_backtest_report_compares_raw_and_calibrated_hgb(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_edge_backtest_report(
        csv_path,
        thresholds=("0.00", "0.05"),
    )

    assert report.row_count == 18
    assert set(report.market_reports) == {"asian_handicap", "total_goals"}
    asian = report.market_reports["asian_handicap"]
    assert set(asian.model_reports) == {
        "raw_hgb_team_form_plus_all_markets",
        "calibrated_hgb_team_form_plus_all_markets",
    }
    calibrated = asian.model_reports["calibrated_hgb_team_form_plus_all_markets"]
    assert calibrated.calibration_method == "sigmoid"
    assert calibrated.feature_count > 0
    assert str(calibrated.threshold_buckets[0].threshold) == "0.0000"
    assert calibrated.threshold_buckets[0].bet_count == 6
    assert calibrated.threshold_buckets[0].accuracy >= 0
    assert calibrated.threshold_buckets[0].roi is not None


def test_format_baseline_edge_backtest_report_includes_threshold_tables(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")
    report = build_baseline_edge_backtest_report(csv_path, thresholds=("0.00",))

    text = format_baseline_edge_backtest_report(report)

    assert "# Baseline Edge Backtest v1" in text
    assert "asian_handicap" in text
    assert "total_goals" in text
    assert "calibrated_hgb_team_form_plus_all_markets" in text
    assert "| Threshold | Bets | Accuracy | Profit | ROI |" in text


def _feature_csv() -> str:
    headers = [
        "match_id",
        "league_name",
        "kickoff_time",
        "split",
        "target_asian_handicap_home_result",
        "target_asian_handicap_away_result",
        "target_total_goals_over_result",
        "target_total_goals_under_result",
        "asian_handicap_home_odds",
        "asian_handicap_away_odds",
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
        "asian_handicap_close_line",
        "asian_handicap_home_implied_probability",
        "asian_handicap_away_implied_probability",
        "asian_handicap_overround",
        "total_goals_close_line",
        "total_goals_over_implied_probability",
        "total_goals_under_implied_probability",
        "total_goals_overround",
    ]
    lines = [",".join(headers)]
    for index in range(1, 19):
        split = "train" if index <= 12 else "validation"
        home_side = index % 2 == 0
        over_side = index % 3 != 0
        home_prob = "0.58" if home_side else "0.42"
        away_prob = "0.42" if home_side else "0.58"
        over_prob = "0.57" if over_side else "0.43"
        under_prob = "0.43" if over_side else "0.57"
        lines.append(
            ",".join(
                [
                    str(index),
                    "Premier League",
                    f"2026-05-{index:02d}T20:00:00",
                    split,
                    "win" if home_side else "loss",
                    "loss" if home_side else "win",
                    "win" if over_side else "loss",
                    "loss" if over_side else "win",
                    "1.900",
                    "1.950",
                    "1.910",
                    "1.940",
                    "5",
                    home_prob,
                    home_prob,
                    "0.1000",
                    away_prob,
                    "1.5000",
                    "1.0000",
                    "3",
                    home_prob,
                    "7.00",
                    "5",
                    away_prob,
                    away_prob,
                    "0.1000",
                    home_prob,
                    "1.0000",
                    "1.5000",
                    "3",
                    away_prob,
                    "7.00",
                    home_prob,
                    "0.2500",
                    away_prob,
                    "1.0400",
                    "-0.25",
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

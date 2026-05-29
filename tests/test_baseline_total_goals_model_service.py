from icewine_prediction.baseline_total_goals_model_service import (
    build_baseline_total_goals_model_report,
    format_baseline_total_goals_model_report,
)


def test_build_baseline_total_goals_model_report_skips_push_rows(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_total_goals_model_report(csv_path)

    assert report.row_count == 10
    assert report.train_rows == 6
    assert report.validation_rows == 3
    assert report.skipped_rows == 1
    assert report.close_market_reference.evaluated_rows == 3
    assert sum(report.close_market_reference.predicted_side_counts.values()) == 3
    assert set(report.model_reports) == {
        "team_form_plus_match_winner_market",
        "team_form_plus_all_markets",
    }
    for model_report in report.model_reports.values():
        assert model_report.model_name == "LogisticRegression"
        assert model_report.feature_count > 0
        assert model_report.accuracy >= 0
        assert model_report.log_loss > 0
        assert model_report.brier_score > 0
        assert sum(model_report.predicted_side_counts.values()) == 3
        assert model_report.calibration_bins


def test_build_baseline_total_goals_model_report_adds_dynamic_models_when_available(tmp_path):
    csv_path = tmp_path / "dynamic_features.csv"
    csv_path.write_text(_feature_csv(include_dynamic=True), encoding="utf-8")

    report = build_baseline_total_goals_model_report(csv_path)

    assert set(report.model_reports) == {
        "team_form_plus_match_winner_market",
        "team_form_plus_all_markets",
        "team_form_plus_all_markets_plus_total_goals_dynamic_core",
        "team_form_plus_all_markets_plus_all_dynamic_core",
        "hgb_team_form_plus_match_winner_market",
        "hgb_team_form_plus_all_markets",
        "hgb_team_form_plus_all_markets_plus_total_goals_dynamic_core",
        "hgb_team_form_plus_all_markets_plus_all_dynamic_core",
    }
    assert (
        report.model_reports["hgb_team_form_plus_all_markets"].model_name
        == "HistGradientBoostingClassifier"
    )
    assert (
        report.model_reports[
            "team_form_plus_all_markets_plus_total_goals_dynamic_core"
        ].feature_count
        > report.model_reports["team_form_plus_all_markets"].feature_count
    )
    assert (
        report.model_reports[
            "team_form_plus_all_markets_plus_all_dynamic_core"
        ].feature_count
        > report.model_reports[
            "team_form_plus_all_markets_plus_total_goals_dynamic_core"
        ].feature_count
    )
    assert (
        report.model_reports[
            "hgb_team_form_plus_all_markets_plus_all_dynamic_core"
        ].feature_count
        == report.model_reports[
            "team_form_plus_all_markets_plus_all_dynamic_core"
        ].feature_count
    )


def test_format_baseline_total_goals_model_report_includes_market_reference(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    text = format_baseline_total_goals_model_report(
        build_baseline_total_goals_model_report(csv_path)
    )

    assert "# Baseline Total Goals Model v1" in text
    assert "close_market_total_goals" in text
    assert "team_form_plus_match_winner_market" in text
    assert "team_form_plus_all_markets" in text
    assert "| Rows | 10 |" in text
    assert "| Skipped rows | 1 |" in text
    assert "## Calibration Buckets" in text


def _feature_csv(*, include_dynamic: bool = False) -> str:
    headers = [
        "match_id",
        "league_name",
        "kickoff_time",
        "split",
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
        "asian_handicap_close_line",
        "asian_handicap_home_implied_probability",
        "asian_handicap_away_implied_probability",
        "asian_handicap_overround",
        "total_goals_over_implied_probability",
        "total_goals_under_implied_probability",
        "total_goals_overround",
    ]
    if include_dynamic:
        headers.extend(_dynamic_headers("asian_handicap", "home", "away"))
        headers.extend(_dynamic_headers("total_goals", "over", "under"))
    lines = [",".join(headers)]
    rows = [
        ("1", "train", "win", "loss", "0.60", "0.40"),
        ("2", "train", "win", "loss", "0.58", "0.42"),
        ("3", "train", "loss", "win", "0.42", "0.58"),
        ("4", "train", "loss", "win", "0.44", "0.56"),
        ("5", "train", "win", "loss", "0.57", "0.43"),
        ("6", "train", "loss", "win", "0.41", "0.59"),
        ("7", "validation", "win", "loss", "0.61", "0.39"),
        ("8", "validation", "loss", "win", "0.40", "0.60"),
        ("9", "validation", "win", "loss", "0.55", "0.45"),
        ("10", "validation", "push", "push", "0.50", "0.50"),
    ]
    for match_id, split, over_result, under_result, over_prob, under_prob in rows:
        values = [
            match_id,
            "Premier League",
            f"2026-05-{int(match_id):02d}T20:00:00",
            split,
            over_result,
            under_result,
            "2.50",
            "1.900",
            "2.000",
            "5",
            over_prob,
            over_prob,
            "0.1000",
            under_prob,
            "1.5000",
            "1.0000",
            "3",
            over_prob,
            "7.00",
            "5",
            under_prob,
            under_prob,
            "0.1000",
            over_prob,
            "1.0000",
            "1.5000",
            "3",
            under_prob,
            "7.00",
            over_prob,
            "0.2500",
            under_prob,
            "1.0400",
            "-0.25",
            "0.5100",
            "0.5100",
            "1.0200",
            over_prob,
            under_prob,
            "1.0200",
        ]
        if include_dynamic:
            values.extend(_dynamic_values("-0.25", over_prob, under_prob))
            values.extend(_dynamic_values("2.50", over_prob, under_prob))
        lines.append(",".join(values))
    return "\n".join(lines) + "\n"


def _dynamic_headers(market: str, side_a: str, side_b: str) -> list[str]:
    headers = []
    for anchor in ("6h", "3h", "1h", "close_anchor"):
        headers.extend(
            [
                f"{market}_{anchor}_line",
                f"{market}_{anchor}_{side_a}_implied_probability",
                f"{market}_{anchor}_{side_b}_implied_probability",
                f"{market}_{anchor}_overround",
                f"{market}_{anchor}_to_close_line_movement",
                f"{market}_{anchor}_to_close_{side_a}_probability_movement",
                f"{market}_{anchor}_to_close_{side_b}_probability_movement",
            ]
        )
    headers.append(f"{market}_snapshot_count")
    return headers


def _dynamic_values(line: str, side_a_probability: str, side_b_probability: str) -> list[str]:
    values = []
    for movement in ("0.25", "0.10", "0.05", "0.00"):
        values.extend(
            [
                line,
                side_a_probability,
                side_b_probability,
                "1.0200",
                movement,
                "0.0100",
                "-0.0100",
            ]
        )
    values.append("42")
    return values

from icewine_prediction.baseline_match_winner_model_service import (
    build_baseline_match_winner_model_report,
    format_baseline_match_winner_model_report,
)


def test_build_baseline_match_winner_model_report_trains_two_logistic_models(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_match_winner_model_report(csv_path)

    assert report.row_count == 9
    assert report.train_rows == 6
    assert report.validation_rows == 3
    assert set(report.model_reports) == {"team_form_only", "team_form_plus_market"}
    for model_report in report.model_reports.values():
        assert model_report.model_name == "LogisticRegression"
        assert model_report.feature_count > 0
        assert model_report.accuracy >= 0
        assert model_report.log_loss > 0
        assert model_report.brier_score > 0
        assert sum(model_report.predicted_result_counts.values()) == 3


def test_format_baseline_match_winner_model_report_includes_metrics(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    text = format_baseline_match_winner_model_report(
        build_baseline_match_winner_model_report(csv_path)
    )

    assert "# Baseline Match Winner Model v1" in text
    assert "LogisticRegression" in text
    assert "team_form_only" in text
    assert "team_form_plus_market" in text
    assert "close_market_match_winner" in text
    assert "1.0055" in text
    assert "| Rows | 9 |" in text
    assert "| Train rows | 6 |" in text
    assert "| Validation rows | 3 |" in text


def _feature_csv() -> str:
    lines = [
        ",".join(
            [
                "match_id",
                "league_name",
                "kickoff_time",
                "split",
                "target_match_result",
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
            ]
        )
    ]
    rows = [
        ("1", "train", "home_win", "3.0", "1.0", "0.0", "0.0", "0.55", "0.25", "0.20"),
        ("2", "train", "home_win", "2.5", "0.8", "0.1", "0.1", "0.54", "0.26", "0.20"),
        ("3", "train", "draw", "1.3", "0.3", "0.4", "0.3", "0.34", "0.36", "0.30"),
        ("4", "train", "draw", "1.1", "0.2", "0.5", "0.3", "0.33", "0.37", "0.30"),
        ("5", "train", "away_win", "0.4", "0.1", "0.1", "0.8", "0.20", "0.25", "0.55"),
        ("6", "train", "away_win", "0.5", "0.1", "0.2", "0.7", "0.21", "0.24", "0.55"),
        ("7", "validation", "home_win", "2.7", "0.9", "0.1", "0.0", "0.56", "0.24", "0.20"),
        ("8", "validation", "draw", "1.0", "0.2", "0.6", "0.2", "0.33", "0.38", "0.29"),
        ("9", "validation", "away_win", "0.6", "0.1", "0.2", "0.7", "0.22", "0.23", "0.55"),
    ]
    for match_id, split, result, ppm, win, draw, loss, home_prob, draw_prob, away_prob in rows:
        lines.append(
            ",".join(
                [
                    match_id,
                    "Premier League",
                    f"2026-05-{int(match_id):02d}T20:00:00",
                    split,
                    result,
                    "5",
                    ppm,
                    win,
                    draw,
                    loss,
                    "1.5000",
                    "1.0000",
                    "3",
                    ppm,
                    "7.00",
                    "5",
                    str(3 - float(ppm)),
                    loss,
                    draw,
                    win,
                    "1.0000",
                    "1.5000",
                    "3",
                    str(3 - float(ppm)),
                    "7.00",
                    home_prob,
                    draw_prob,
                    away_prob,
                    "1.0400",
                ]
            )
        )
    return "\n".join(lines) + "\n"

from decimal import Decimal

from icewine_prediction.baseline_recommendation_sandbox_service import (
    build_baseline_recommendation_sandbox_report,
    format_baseline_recommendation_sandbox_report,
)


def test_build_baseline_recommendation_sandbox_report_lists_asian_handicap_candidates(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_recommendation_sandbox_report(
        csv_path,
        edge_threshold="0.00",
        top_n=4,
    )

    assert report.row_count == 24
    assert report.train_rows == 16
    assert report.validation_rows == 8
    assert report.edge_threshold == Decimal("0.0000")
    assert report.total_candidates == 8
    assert report.total_profit is not None
    assert report.roi is not None
    assert report.candidates
    assert report.candidates[0].market_type == "asian_handicap"
    assert report.candidates[0].side in {"home_cover", "away_cover"}
    assert report.candidates[0].edge >= Decimal("0.0000")
    assert report.candidates[0].profit in {Decimal("0.9000"), Decimal("-1.0000")}
    assert report.side_summaries
    assert report.league_summaries


def test_format_baseline_recommendation_sandbox_report_includes_candidate_table(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")
    report = build_baseline_recommendation_sandbox_report(
        csv_path,
        edge_threshold="0.00",
        top_n=3,
    )

    text = format_baseline_recommendation_sandbox_report(report)

    assert "# Baseline Recommendation Sandbox v1" in text
    assert "asian_handicap raw_hgb_team_form_plus_all_markets" in text
    assert "| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |" in text


def _feature_csv() -> str:
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
    for index in range(1, 25):
        split = "train" if index <= 16 else "validation"
        home_side = index % 2 == 0
        home_prob = "0.70" if home_side else "0.30"
        away_prob = "0.30" if home_side else "0.70"
        lines.append(
            ",".join(
                [
                    str(index),
                    "Premier League" if index <= 12 else "La Liga",
                    f"2026-05-{index:02d}T20:00:00",
                    split,
                    f"Home {index}",
                    f"Away {index}",
                    "win" if home_side else "loss",
                    "loss" if home_side else "win",
                    "-0.25",
                    "1.900",
                    "1.900",
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

from pathlib import Path

from icewine_prediction.baseline_training_dataset_qa_service import (
    build_baseline_training_dataset_qa_report,
    format_baseline_training_dataset_qa_report,
)


def test_build_baseline_training_dataset_qa_report_summarizes_csv_quality(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                ",".join(
                    [
                        "match_id",
                        "season",
                        "kickoff_time",
                        "league_name",
                        "match_result",
                        "total_goals",
                        "asian_handicap_close_line",
                        "asian_handicap_home_odds",
                        "asian_handicap_away_odds",
                        "asian_handicap_home_implied_probability",
                        "asian_handicap_away_implied_probability",
                        "asian_handicap_overround",
                        "asian_handicap_home_result",
                        "asian_handicap_away_result",
                        "total_goals_close_line",
                        "total_goals_over_odds",
                        "total_goals_under_odds",
                        "total_goals_over_implied_probability",
                        "total_goals_under_implied_probability",
                        "total_goals_overround",
                        "total_goals_over_result",
                        "total_goals_under_result",
                        "match_winner_home_odds",
                        "match_winner_draw_odds",
                        "match_winner_away_odds",
                        "match_winner_home_implied_probability",
                        "match_winner_draw_implied_probability",
                        "match_winner_away_implied_probability",
                        "match_winner_overround",
                        "match_winner_home_result",
                        "match_winner_draw_result",
                        "match_winner_away_result",
                        "asian_handicap_snapshot_count",
                        "total_goals_snapshot_count",
                        "match_winner_snapshot_count",
                        "quality_tags",
                    ]
                ),
                ",".join(
                    [
                        "1",
                        "2026",
                        "2026-05-01T20:00:00",
                        "Premier League",
                        "home_win",
                        "3",
                        "-0.25",
                        "1.900",
                        "2.000",
                        "0.5263",
                        "0.5000",
                        "1.0263",
                        "win",
                        "loss",
                        "2.50",
                        "1.950",
                        "1.950",
                        "0.5128",
                        "0.5128",
                        "1.0256",
                        "win",
                        "loss",
                        "2.100",
                        "3.300",
                        "3.600",
                        "0.4762",
                        "0.3030",
                        "0.2778",
                        "1.0570",
                        "win",
                        "loss",
                        "loss",
                        "40",
                        "38",
                        "42",
                        "",
                    ]
                ),
                ",".join(
                    [
                        "2",
                        "2026",
                        "2026-05-02T20:00:00",
                        "Premier League",
                        "draw",
                        "2",
                        "0.00",
                        "1.950",
                        "1.950",
                        "0.5128",
                        "0.5128",
                        "1.0256",
                        "push",
                        "push",
                        "2.25",
                        "1.850",
                        "2.050",
                        "0.5405",
                        "0.4878",
                        "1.0283",
                        "half_loss",
                        "half_win",
                        "2.800",
                        "3.100",
                        "2.800",
                        "0.3571",
                        "0.3226",
                        "0.3571",
                        "1.0368",
                        "loss",
                        "win",
                        "loss",
                        "12",
                        "12",
                        "12",
                        "thin_history",
                    ]
                ),
                ",".join(
                    [
                        "3",
                        "2025",
                        "2026-05-03T20:00:00",
                        "La Liga",
                        "away_win",
                        "1",
                        "0.50",
                        "1.800",
                        "2.100",
                        "0.5556",
                        "0.4762",
                        "1.0318",
                        "loss",
                        "win",
                        "2.00",
                        "1.900",
                        "2.000",
                        "0.5263",
                        "0.5000",
                        "1.0263",
                        "loss",
                        "win",
                        "3.200",
                        "3.200",
                        "2.300",
                        "0.3125",
                        "0.3125",
                        "0.4348",
                        "1.0598",
                        "loss",
                        "loss",
                        "win",
                        "8",
                        "8",
                        "8",
                        "thin_history",
                    ]
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_baseline_training_dataset_qa_report(csv_path)

    assert report.row_count == 3
    assert report.empty_required_cells == {}
    assert report.by_season == {"2026": 2, "2025": 1}
    assert report.match_result_counts == {"home_win": 1, "draw": 1, "away_win": 1}
    assert report.thin_history_count == 2
    assert report.thin_history_ratio == "0.6667"
    assert report.league_counts == {"Premier League": 2, "La Liga": 1}
    assert report.low_sample_leagues == {"La Liga": 1, "Premier League": 2}
    assert report.overround_ranges["match_winner"] == ("1.0368", "1.0598")
    assert report.invalid_odds_cells == {}
    assert report.invalid_probability_cells == {}
    assert report.invalid_overround_cells == {}


def test_format_baseline_training_dataset_qa_report_includes_core_sections(tmp_path):
    csv_path = Path(tmp_path / "baseline.csv")
    csv_path.write_text(
        "match_id,season,kickoff_time,league_name,match_result,total_goals,"
        "asian_handicap_close_line,asian_handicap_home_odds,asian_handicap_away_odds,"
        "asian_handicap_home_implied_probability,asian_handicap_away_implied_probability,"
        "asian_handicap_overround,asian_handicap_home_result,asian_handicap_away_result,"
        "total_goals_close_line,total_goals_over_odds,total_goals_under_odds,"
        "total_goals_over_implied_probability,total_goals_under_implied_probability,"
        "total_goals_overround,total_goals_over_result,total_goals_under_result,"
        "match_winner_home_odds,match_winner_draw_odds,match_winner_away_odds,"
        "match_winner_home_implied_probability,match_winner_draw_implied_probability,"
        "match_winner_away_implied_probability,match_winner_overround,"
        "match_winner_home_result,match_winner_draw_result,match_winner_away_result,"
        "asian_handicap_snapshot_count,total_goals_snapshot_count,"
        "match_winner_snapshot_count,quality_tags\n"
        "1,2026,2026-05-01T20:00:00,Premier League,home_win,3,"
        "-0.25,1.900,2.000,0.5263,0.5000,1.0263,win,loss,"
        "2.50,1.950,1.950,0.5128,0.5128,1.0256,win,loss,"
        "2.100,3.300,3.600,0.4762,0.3030,0.2778,1.0570,win,loss,loss,"
        "40,38,42,\n",
        encoding="utf-8",
    )

    text = format_baseline_training_dataset_qa_report(
        build_baseline_training_dataset_qa_report(csv_path)
    )

    assert "# Baseline Training Dataset QA" in text
    assert "Rows | 1" in text
    assert "Empty required cells | 0" in text
    assert "## Overround Ranges" in text
    assert "## Result Labels" in text

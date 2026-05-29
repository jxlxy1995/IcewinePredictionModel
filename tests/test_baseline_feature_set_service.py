from pathlib import Path

from icewine_prediction.baseline_feature_set_service import (
    build_baseline_feature_set,
    format_baseline_feature_set_report,
    write_baseline_feature_set_csv,
)


def test_build_baseline_feature_set_uses_only_prior_team_history(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                _header(),
                _row(
                    match_id="1",
                    kickoff_time="2026-01-20T20:00:00",
                    home="Alpha",
                    away="Beta",
                    home_score="2",
                    away_score="1",
                    result="home_win",
                ),
                _row(
                    match_id="2",
                    kickoff_time="2026-01-27T20:00:00",
                    home="Beta",
                    away="Alpha",
                    home_score="0",
                    away_score="0",
                    result="draw",
                ),
                _row(
                    match_id="3",
                    kickoff_time="2026-02-03T20:00:00",
                    home="Alpha",
                    away="Beta",
                    home_score="1",
                    away_score="3",
                    result="away_win",
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_set = build_baseline_feature_set(csv_path, validation_ratio=0.34)

    rows = feature_set.rows
    assert [row["match_id"] for row in rows] == ["1", "2", "3"]
    assert rows[0]["split"] == "train"
    assert rows[0]["home_prior_matches"] == "0"
    assert rows[0]["away_prior_matches"] == "0"
    assert rows[0]["target_asian_handicap_home_result"] == "win"
    assert rows[0]["target_asian_handicap_away_result"] == "loss"
    assert rows[0]["asian_handicap_home_odds"] == "1.900"
    assert rows[0]["asian_handicap_away_odds"] == "2.000"
    assert rows[1]["home_prior_matches"] == "1"
    assert rows[1]["home_prior_points_per_match"] == "0.0000"
    assert rows[1]["away_prior_points_per_match"] == "3.0000"
    assert rows[1]["home_rest_days"] == "7.00"
    assert rows[1]["away_rest_days"] == "7.00"
    assert rows[2]["split"] == "validation"
    assert rows[2]["home_prior_matches"] == "2"
    assert rows[2]["home_prior_goals_for_per_match"] == "1.0000"
    assert rows[2]["home_prior_goals_against_per_match"] == "0.5000"
    assert rows[2]["away_prior_matches"] == "2"
    assert rows[2]["away_prior_goals_for_per_match"] == "0.5000"
    assert rows[2]["away_prior_goals_against_per_match"] == "1.0000"
    assert feature_set.report.train_rows == 2
    assert feature_set.report.validation_rows == 1


def test_format_baseline_feature_set_report_summarizes_time_split(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                _header(),
                _row(match_id="1", kickoff_time="2026-01-20T20:00:00"),
                _row(match_id="2", kickoff_time="2026-01-27T20:00:00"),
                _row(match_id="3", kickoff_time="2026-02-03T20:00:00"),
                _row(match_id="4", kickoff_time="2026-02-10T20:00:00"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    text = format_baseline_feature_set_report(
        build_baseline_feature_set(csv_path, validation_ratio=0.25).report
    )

    assert "# Baseline Feature Set v1" in text
    assert "Rows | 4" in text
    assert "Train rows | 3" in text
    assert "Validation rows | 1" in text
    assert "Validation start | 2026-02-10T20:00:00" in text
    assert "| Premier League | 4 | 3 | 1 |" in text


def test_write_baseline_feature_set_csv_uses_stable_field_order(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    output_path = tmp_path / "features.csv"
    csv_path.write_text(
        "\n".join([_header(), _row(match_id="1", kickoff_time="2026-01-20T20:00:00")]) + "\n",
        encoding="utf-8",
    )

    write_baseline_feature_set_csv(build_baseline_feature_set(csv_path), output_path)

    text = output_path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith("match_id,source_match_id,league_name")
    assert "home_prior_points_per_match" in first_line
    assert "match_winner_home_implied_probability" in first_line


def test_build_baseline_feature_set_keeps_same_kickoff_in_same_split(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                _header(),
                _row(match_id="1", kickoff_time="2026-01-20T20:00:00"),
                _row(match_id="2", kickoff_time="2026-01-27T20:00:00"),
                _row(match_id="3", kickoff_time="2026-02-03T20:00:00"),
                _row(match_id="4", kickoff_time="2026-02-03T20:00:00"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    feature_set = build_baseline_feature_set(csv_path, validation_ratio=0.25)

    assert [row["split"] for row in feature_set.rows] == [
        "train",
        "train",
        "validation",
        "validation",
    ]
    assert feature_set.report.train_rows == 2
    assert feature_set.report.validation_rows == 2


def _header() -> str:
    return ",".join(
        [
            "match_id",
            "source_match_id",
            "league_name",
            "league_source_id",
            "season",
            "kickoff_time",
            "home_team_name",
            "away_team_name",
            "home_score",
            "away_score",
            "match_result",
            "total_goals",
            "asian_handicap_home_result",
            "asian_handicap_away_result",
            "asian_handicap_close_line",
            "asian_handicap_home_odds",
            "asian_handicap_away_odds",
            "asian_handicap_home_implied_probability",
            "asian_handicap_away_implied_probability",
            "asian_handicap_overround",
            "total_goals_close_line",
            "total_goals_over_implied_probability",
            "total_goals_under_implied_probability",
            "total_goals_overround",
            "match_winner_home_implied_probability",
            "match_winner_draw_implied_probability",
            "match_winner_away_implied_probability",
            "match_winner_overround",
            "quality_tags",
        ]
    )


def _row(
    *,
    match_id: str,
    kickoff_time: str,
    home: str = "Alpha",
    away: str = "Beta",
    home_score: str = "2",
    away_score: str = "1",
    result: str = "home_win",
) -> str:
    return ",".join(
        [
            match_id,
            f"fixture-{match_id}",
            "Premier League",
            "39",
            "2026",
            kickoff_time,
            home,
            away,
            home_score,
            away_score,
            result,
            str(int(home_score) + int(away_score)),
            "win",
            "loss",
            "-0.25",
            "1.900",
            "2.000",
            "0.5200",
            "0.5000",
            "1.0200",
            "2.50",
            "0.5100",
            "0.5100",
            "1.0200",
            "0.4600",
            "0.2800",
            "0.3000",
            "1.0400",
            "",
        ]
    )

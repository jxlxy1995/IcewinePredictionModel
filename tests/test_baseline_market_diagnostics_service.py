from icewine_prediction.baseline_market_diagnostics_service import (
    build_baseline_market_diagnostics_report,
    format_baseline_market_diagnostics_report,
)


def test_build_baseline_market_diagnostics_report_segments_validation_rows(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    report = build_baseline_market_diagnostics_report(csv_path, min_segment_rows=1)

    assert report.csv_path == csv_path
    assert report.row_count == 8
    assert report.validation_rows == 6
    assert report.market_reports["asian_handicap"].eligible_rows == 5
    assert report.market_reports["total_goals"].eligible_rows == 5
    assert report.market_reports["asian_handicap"].overall.accuracy == "0.6000"
    assert report.market_reports["total_goals"].overall.accuracy == "0.4000"
    assert len(report.market_reports["asian_handicap"].by_league) == 2
    assert len(report.market_reports["asian_handicap"].by_line) == 2
    assert len(report.market_reports["total_goals"].by_market_confidence) == 2
    assert report.market_reports["total_goals"].actual_side_counts == {"over": 3, "under": 2}


def test_format_baseline_market_diagnostics_report_includes_key_segments(tmp_path):
    csv_path = tmp_path / "features.csv"
    csv_path.write_text(_feature_csv(), encoding="utf-8")

    text = format_baseline_market_diagnostics_report(
        build_baseline_market_diagnostics_report(csv_path, min_segment_rows=1)
    )

    assert "# Baseline Market Diagnostics v1" in text
    assert "## Asian Handicap" in text
    assert "## Total Goals" in text
    assert "### By League" in text
    assert "### By Line" in text
    assert "### By Market Confidence" in text
    assert "Premier League" in text
    assert "2.50" in text


def _feature_csv() -> str:
    lines = [
        ",".join(
            [
                "match_id",
                "league_name",
                "kickoff_time",
                "split",
                "target_asian_handicap_home_result",
                "target_asian_handicap_away_result",
                "asian_handicap_close_line",
                "asian_handicap_home_implied_probability",
                "asian_handicap_away_implied_probability",
                "target_total_goals_over_result",
                "target_total_goals_under_result",
                "total_goals_close_line",
                "total_goals_over_implied_probability",
                "total_goals_under_implied_probability",
            ]
        )
    ]
    rows = [
        ("1", "train", "Premier League", "win", "loss", "-0.25", "0.60", "0.40", "win", "loss", "2.50", "0.60", "0.40"),
        ("2", "train", "Premier League", "loss", "win", "0.25", "0.42", "0.58", "loss", "win", "2.75", "0.42", "0.58"),
        ("3", "validation", "Premier League", "win", "loss", "-0.25", "0.60", "0.40", "win", "loss", "2.50", "0.60", "0.40"),
        ("4", "validation", "Premier League", "loss", "win", "-0.25", "0.61", "0.39", "loss", "win", "2.50", "0.62", "0.38"),
        ("5", "validation", "Premier League", "loss", "win", "0.25", "0.40", "0.60", "win", "loss", "2.75", "0.41", "0.59"),
        ("6", "validation", "Championship", "win", "loss", "0.25", "0.45", "0.55", "win", "loss", "2.75", "0.45", "0.55"),
        ("7", "validation", "Championship", "loss", "win", "0.25", "0.48", "0.52", "loss", "win", "2.75", "0.48", "0.52"),
        ("8", "validation", "Championship", "push", "push", "0.25", "0.50", "0.50", "push", "push", "3.00", "0.50", "0.50"),
    ]
    for (
        match_id,
        split,
        league_name,
        ah_home_result,
        ah_away_result,
        ah_line,
        ah_home_prob,
        ah_away_prob,
        tg_over_result,
        tg_under_result,
        tg_line,
        tg_over_prob,
        tg_under_prob,
    ) in rows:
        lines.append(
            ",".join(
                [
                    match_id,
                    league_name,
                    f"2026-05-{int(match_id):02d}T20:00:00",
                    split,
                    ah_home_result,
                    ah_away_result,
                    ah_line,
                    ah_home_prob,
                    ah_away_prob,
                    tg_over_result,
                    tg_under_result,
                    tg_line,
                    tg_over_prob,
                    tg_under_prob,
                ]
            )
        )
    return "\n".join(lines) + "\n"

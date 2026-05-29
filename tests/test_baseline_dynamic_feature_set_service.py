from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from icewine_prediction.baseline_dynamic_feature_set_service import (
    BaselineDynamicFeatureSet,
    BaselineDynamicFeatureSetReport,
    build_baseline_dynamic_feature_set,
    format_baseline_dynamic_feature_set_report,
    write_baseline_dynamic_feature_set_csv,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


UTC = ZoneInfo("UTC")


def test_build_baseline_dynamic_feature_set_adds_anchor_movement_fields(session, tmp_path):
    league = League(name="Premier League", country_or_region="England", level=1)
    session.add(league)
    session.flush()
    match = _add_match(
        session,
        league,
        match_id_source="fixture-1",
        kickoff_time=datetime(2026, 1, 20, 20, 0, tzinfo=UTC),
    )
    for label, minutes, asian_line, total_line, asian_home_odds, total_over_odds in [
        ("12h", 720, Decimal("-0.25"), Decimal("2.50"), Decimal("1.90"), Decimal("1.88")),
        ("6h", 360, Decimal("-0.50"), Decimal("2.50"), Decimal("1.86"), Decimal("1.92")),
        ("3h", 180, Decimal("-0.50"), Decimal("2.75"), Decimal("1.84"), Decimal("1.95")),
        ("1h", 60, Decimal("-0.75"), Decimal("2.75"), Decimal("1.82"), Decimal("1.98")),
        ("close", 7, Decimal("-0.75"), Decimal("2.75"), Decimal("1.80"), Decimal("2.00")),
    ]:
        snapshot_time = match.kickoff_time - timedelta(minutes=minutes)
        _add_pair(
            session,
            match,
            market_type="asian_handicap",
            market_line=asian_line,
            snapshot_time=snapshot_time,
            side_a="home",
            side_b="away",
            side_a_odds=asian_home_odds,
            side_b_odds=Decimal("2.00"),
            market_id=f"ah-{label}",
        )
        _add_pair(
            session,
            match,
            market_type="total_goals",
            market_line=total_line,
            snapshot_time=snapshot_time,
            side_a="over",
            side_b="under",
            side_a_odds=total_over_odds,
            side_b_odds=Decimal("1.90"),
            market_id=f"ou-{label}",
        )
    session.commit()
    static_csv = tmp_path / "features.csv"
    static_csv.write_text(_static_feature_csv(), encoding="utf-8")

    feature_set = build_baseline_dynamic_feature_set(session, static_csv)

    assert feature_set.report.row_count == 1
    assert feature_set.report.rows_with_asian_handicap_dynamic == 1
    assert feature_set.report.rows_with_total_goals_dynamic == 1
    assert feature_set.report.complete_core_anchor_rows == 1
    row = feature_set.rows[0]
    assert len(feature_set.fieldnames) == len(set(feature_set.fieldnames))
    assert row["asian_handicap_6h_line"] == "-0.50"
    assert row["asian_handicap_6h_to_close_line_movement"] == "-0.25"
    assert row["asian_handicap_6h_home_implied_probability"] == "0.5376"
    assert row["asian_handicap_6h_to_close_home_probability_movement"] == "0.0180"
    assert row["asian_handicap_24h_line"] == ""
    assert row["asian_handicap_close_anchor_line"] == "-0.75"
    assert row["total_goals_3h_line"] == "2.75"
    assert row["total_goals_3h_to_close_line_movement"] == "0.00"
    assert row["total_goals_12h_to_close_over_probability_movement"] == "-0.0319"


def test_write_and_format_baseline_dynamic_feature_set(tmp_path):
    feature_set = BaselineDynamicFeatureSet(
        rows=[
            {
                "match_id": "1",
                "split": "train",
                "asian_handicap_6h_line": "-0.50",
                "total_goals_6h_line": "2.50",
            }
        ],
        fieldnames=("match_id", "split", "asian_handicap_6h_line", "total_goals_6h_line"),
        report=BaselineDynamicFeatureSetReport(
            source_csv_path=Path("features.csv"),
            row_count=1,
            rows_with_asian_handicap_dynamic=1,
            rows_with_total_goals_dynamic=1,
            complete_core_anchor_rows=1,
        ),
    )
    output_path = tmp_path / "dynamic.csv"

    write_baseline_dynamic_feature_set_csv(feature_set, output_path)
    report_text = format_baseline_dynamic_feature_set_report(feature_set.report)

    csv_text = output_path.read_text(encoding="utf-8")
    assert "asian_handicap_6h_line" in csv_text.splitlines()[0]
    assert "# Baseline Dynamic Feature Set v1" in report_text
    assert "Rows | 1" in report_text


def _static_feature_csv() -> str:
    return "\n".join(
        [
            ",".join(
                [
                    "match_id",
                    "source_match_id",
                    "league_name",
                    "season",
                    "kickoff_time",
                    "split",
                    "home_team_name",
                    "away_team_name",
                    "asian_handicap_close_line",
                    "total_goals_close_line",
                ]
            ),
            "1,fixture-1,Premier League,2026,2026-01-20T20:00:00,train,Arsenal,Chelsea,-0.75,2.75",
        ]
    ) + "\n"


def _add_match(
    session,
    league: League,
    *,
    match_id_source: str,
    kickoff_time: datetime,
) -> Match:
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time,
        season=2026,
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api-football",
        source_match_id=match_id_source,
    )
    session.add(match)
    session.flush()
    return match


def _add_pair(
    session,
    match: Match,
    *,
    market_type: str,
    market_line: Decimal,
    snapshot_time: datetime,
    side_a: str,
    side_b: str,
    side_a_odds: Decimal,
    side_b_odds: Decimal,
    market_id: str,
) -> None:
    for side, odds in [(side_a, side_a_odds), (side_b, side_b_odds)]:
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=f"fixture-{match.id}",
                bookmaker="pinnacle",
                market_type=market_type,
                market_id=market_id,
                market_name=market_type,
                market_line=market_line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )

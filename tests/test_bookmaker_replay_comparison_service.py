from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from icewine_prediction.bookmaker_replay_comparison_service import (
    build_bookmaker_replay_comparison_report,
    format_bookmaker_replay_comparison_report,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team
from icewine_prediction.paper_recommendation_queue_service import PaperQueueRow


UTC = ZoneInfo("UTC")


def test_build_bookmaker_replay_comparison_report_compares_same_overlap_matches(
    session,
    tmp_path,
    monkeypatch,
):
    feature_csv = tmp_path / "features.csv"
    feature_csv.write_text(
        "match_id,kickoff_time,split\n"
        "1,2026-05-01T20:00:00+00:00,train\n"
        "2,2026-05-02T20:00:00+00:00,validation\n"
        "3,2026-05-03T20:00:00+00:00,validation\n",
        encoding="utf-8",
    )
    overlap_match = _add_finished_match(session, match_id=2, home_score=0, away_score=1)
    baseline_only_match = _add_finished_match(session, match_id=3, home_score=2, away_score=0)
    baseline_snapshots = {
        overlap_match.id: [_snapshot(overlap_match.id, "pinnacle")],
        baseline_only_match.id: [_snapshot(baseline_only_match.id, "pinnacle")],
    }
    candidate_snapshots = {
        overlap_match.id: [_snapshot(overlap_match.id, "sbobet")],
    }

    monkeypatch.setattr(
        "icewine_prediction.bookmaker_replay_comparison_service.train_paper_queue_scorer_from_rows",
        lambda rows: (lambda row: None),
    )
    monkeypatch.setattr(
        "icewine_prediction.bookmaker_replay_comparison_service._load_matches_by_id",
        lambda session, match_ids: {
            overlap_match.id: overlap_match,
            baseline_only_match.id: baseline_only_match,
        },
    )
    monkeypatch.setattr(
        "icewine_prediction.bookmaker_replay_comparison_service._load_snapshots_by_match_id",
        lambda session, *, match_ids, source_name, bookmaker: (
            baseline_snapshots if bookmaker == "pinnacle" else candidate_snapshots
        ),
    )
    monkeypatch.setattr(
        "icewine_prediction.bookmaker_replay_comparison_service._team_prior_states_by_match",
        lambda session, matches: {},
    )

    def fake_build_rows(
        match,
        *,
        scorer,
        edge_threshold,
        display_name_service,
        historical_snapshots,
        team_prior_states,
    ):
        bookmaker = historical_snapshots[0].bookmaker
        if match.id != overlap_match.id:
            raise AssertionError("only overlap match should be replayed")
        if bookmaker == "pinnacle":
            return [
                _candidate_row(
                    match.id,
                    strategy_key="asian_away_cover_hgb_edge_v1",
                    market_type="asian_handicap",
                    side="away_cover",
                    line=Decimal("0.25"),
                    odds=Decimal("1.950"),
                    edge=Decimal("0.1200"),
                ),
                _candidate_row(
                    match.id,
                    strategy_key="total_goals_hgb_edge_v1",
                    market_type="total_goals",
                    side="over",
                    line=Decimal("2.50"),
                    odds=Decimal("1.920"),
                    edge=Decimal("0.1100"),
                ),
            ]
        return [
            _candidate_row(
                match.id,
                strategy_key="asian_away_cover_hgb_edge_v1",
                market_type="asian_handicap",
                side="away_cover",
                line=Decimal("0.00"),
                odds=Decimal("1.900"),
                edge=Decimal("0.1000"),
            )
        ]

    monkeypatch.setattr(
        "icewine_prediction.bookmaker_replay_comparison_service.build_paper_recommendation_rows_for_match",
        fake_build_rows,
    )

    report = build_bookmaker_replay_comparison_report(
        session,
        csv_path=feature_csv,
        baseline_bookmaker="pinnacle",
        candidate_bookmaker="sbobet",
    )

    assert report.baseline_bookmaker == "pinnacle"
    assert report.candidate_bookmaker == "sbobet"
    assert report.row_count == 3
    assert report.train_rows == 1
    assert report.validation_rows == 2
    assert report.baseline_snapshot_match_count == 2
    assert report.candidate_snapshot_match_count == 1
    assert report.overlap_match_count == 1
    assert report.baseline_candidate_count == 2
    assert report.candidate_candidate_count == 1
    assert report.overlap_candidate_count == 1
    assert report.baseline_only_candidate_count == 1
    assert report.candidate_only_candidate_count == 0

    asian = report.strategy_summaries[0]
    assert asian.strategy_key == "asian_away_cover_hgb_edge_v1"
    assert asian.baseline_candidate_count == 1
    assert asian.candidate_candidate_count == 1
    assert asian.overlap_candidate_count == 1
    assert asian.baseline_profit == Decimal("0.9500")
    assert asian.candidate_profit == Decimal("0.9000")
    assert asian.overlap_baseline_profit == Decimal("0.9500")
    assert asian.overlap_candidate_profit == Decimal("0.9000")
    assert asian.overlap_avg_abs_line_diff == Decimal("0.2500")
    assert asian.overlap_avg_abs_odds_diff == Decimal("0.0500")

    total = report.strategy_summaries[1]
    assert total.strategy_key == "total_goals_hgb_edge_v1"
    assert total.baseline_candidate_count == 1
    assert total.candidate_candidate_count == 0
    assert total.overlap_candidate_count == 0
    assert total.baseline_only_candidate_count == 1
    assert total.baseline_profit == Decimal("-1.0000")
    assert total.candidate_profit == Decimal("0.0000")

    output = format_bookmaker_replay_comparison_report(report)

    assert "# Bookmaker Replay Comparison" in output
    assert "| `asian_away_cover_hgb_edge_v1` | 1 | 1 | 1 | 0 | 0 | 0.9500 | 0.9000 |" in output
    assert "| `total_goals_hgb_edge_v1` | 1 | 0 | 0 | 1 | 0 | -1.0000 | 0.0000 |" in output


def _add_finished_match(session, *, match_id: int, home_score: int, away_score: int) -> Match:
    league = League(name=f"League {match_id}", country_or_region="Test", level=1, is_enabled=True)
    home = Team(canonical_name=f"Home {match_id}")
    away = Team(canonical_name=f"Away {match_id}")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        id=match_id,
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, match_id, 20, 0, tzinfo=UTC),
        status="finished",
        home_score=home_score,
        away_score=away_score,
        source_name="api-football",
        source_match_id=str(match_id),
    )
    session.add(match)
    session.flush()
    return match


def _snapshot(match_id: int, bookmaker: str) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name="oddspapi",
        source_fixture_id=f"fixture-{match_id}",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"{bookmaker}-{match_id}",
        market_name="asian_handicap",
        market_line=Decimal("0.25"),
        outcome_side="away",
        odds=Decimal("1.900"),
        snapshot_time=datetime(2026, 5, match_id, 19, 50, tzinfo=UTC),
        period="fulltime",
    )


def _candidate_row(
    match_id: int,
    *,
    strategy_key: str,
    market_type: str,
    side: str,
    line: Decimal,
    odds: Decimal,
    edge: Decimal,
) -> PaperQueueRow:
    return PaperQueueRow(
        match_id=match_id,
        source_match_id=str(match_id),
        kickoff_time="2026-05-02T20:00:00+00:00",
        league_name="Test League",
        league_display_name="Test League",
        home_team_name="Home",
        home_team_display_name="Home",
        away_team_name="Away",
        away_team_display_name="Away",
        status="candidate",
        market_type=market_type,
        line=line,
        side=side,
        recommended_handicap=None,
        odds=odds,
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=edge,
        line_bucket="test_bucket",
        risk_tags=(),
        strategy_key=strategy_key,
        strategy_display_name=strategy_key,
        signal_version="v1",
        odds_source="oddspapi_historical",
    )

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueScore,
    build_paper_recommendation_queue,
    format_paper_recommendation_queue_report,
)


def test_build_paper_recommendation_queue_marks_candidate_no_odds_and_prefetch(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    other_home = Team(canonical_name="Molde")
    other_away = Team(canonical_name="Tromso")
    session.add_all([league, home, away, other_home, other_away])
    session.flush()
    now = datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    session.add_all(
        [
            Match(
                league=league,
                home_team=home,
                away_team=other_away,
                kickoff_time=datetime(2026, 5, 23, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=2,
                away_score=0,
                source_name="api_football",
                source_match_id="home-history",
            ),
            Match(
                league=league,
                home_team=other_home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 24, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=1,
                away_score=1,
                source_name="api_football",
                source_match_id="away-history",
            ),
        ]
    )
    priced = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="priced",
    )
    no_odds = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 2, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="no-odds",
    )
    session.add_all([priced, no_odds])
    session.flush()
    session.add(
        OddsSnapshot(
            match=priced,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("0.25"),
            home_odds=Decimal("1.95"),
            away_odds=Decimal("1.95"),
            total_line=Decimal("2.75"),
            over_odds=Decimal("1.90"),
            under_odds=Decimal("2.00"),
            match_winner_home_odds=Decimal("2.10"),
            match_winner_draw_odds=Decimal("3.25"),
            match_winner_away_odds=Decimal("3.40"),
        )
    )
    session.commit()
    prefetched = []

    def fake_prefetch(fixture_ids):
        prefetched.extend(fixture_ids)
        return {"created": 1, "skipped": 0, "failed_fixture_id": None, "error_message": None}

    def fake_scorer(row):
        if row["match_id"] != str(priced.id):
            return None
        assert row["home_prior_matches"] == "1"
        assert row["home_prior_home_matches"] == "1"
        assert row["home_prior_points_per_match"] == "3.0000"
        assert row["away_prior_matches"] == "1"
        assert row["away_prior_away_matches"] == "1"
        assert row["away_prior_points_per_match"] == "1.0000"
        assert row["match_winner_home_implied_probability"] == "0.4762"
        assert row["match_winner_draw_implied_probability"] == "0.3077"
        assert row["match_winner_away_implied_probability"] == "0.2941"
        assert row["match_winner_overround"] == "1.0780"
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        near_start_hours=3,
        edge_threshold="0.10",
        prefetch_odds=True,
        odds_prefetcher=fake_prefetch,
        scorer=fake_scorer,
    )

    assert prefetched == ["priced", "no-odds"]
    assert report.near_start_fixture_ids == ["priced", "no-odds"]
    assert report.prefetch_result == {
        "created": 1,
        "skipped": 0,
        "failed_fixture_id": None,
        "error_message": None,
    }
    assert report.total_matches == 2
    assert report.candidate_count == 1
    statuses = {row.source_match_id: row.status for row in report.rows}
    assert statuses == {"priced": "candidate", "no-odds": "no_odds"}
    candidate = next(row for row in report.rows if row.status == "candidate")
    assert candidate.line_bucket == "away_favorite"
    assert candidate.risk_tags == ("line_bucket:away_favorite",)
    assert candidate.recommended_handicap == "客队 -0.25"


def test_build_paper_recommendation_queue_requires_odds_within_three_hours_before_kickoff(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    now = datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="priced-too-early",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=datetime(2026, 5, 29, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.99"),
            away_odds=Decimal("1.93"),
            total_line=Decimal("2.50"),
            over_odds=Decimal("1.90"),
            under_odds=Decimal("2.00"),
            match_winner_home_odds=Decimal("2.10"),
            match_winner_draw_odds=Decimal("3.25"),
            match_winner_away_odds=Decimal("3.40"),
        )
    )
    session.commit()

    def fake_scorer(row):
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    assert report.candidate_count == 0
    assert report.rows[0].status == "stale_odds"


def test_build_paper_recommendation_queue_adds_v2_bucket_strategy_candidate(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    now = datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="priced",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.95"),
            away_odds=Decimal("1.95"),
            total_line=Decimal("2.75"),
            over_odds=Decimal("1.90"),
            under_odds=Decimal("2.00"),
            match_winner_home_odds=Decimal("2.10"),
            match_winner_draw_odds=Decimal("3.25"),
            match_winner_away_odds=Decimal("3.40"),
        )
    )
    session.commit()

    def fake_scorer(row):
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.7100"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2100"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    candidate_keys = {
        row.strategy_key
        for row in report.rows
        if row.status == "candidate"
    }
    assert candidate_keys == {
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    }
    v2 = next(row for row in report.rows if row.strategy_key == "asian_away_cover_hgb_bucket_v2")
    assert v2.strategy_display_name == "亚盘客队方向 · HGB分盘口桶 v2"
    assert v2.line_bucket == "away_underdog"
    assert v2.risk_tags == ("line_bucket:away_underdog", "strategy:bucket_v2")


def test_format_paper_recommendation_queue_report_includes_candidate_detail(session):
    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=1,
        scorer=lambda row: None,
    )

    text = format_paper_recommendation_queue_report(report)

    assert "Paper Recommendation Queue v1" in text
    assert "Recommended handicap" in text
    assert "Candidates" in text
    assert str(report.total_matches) in text

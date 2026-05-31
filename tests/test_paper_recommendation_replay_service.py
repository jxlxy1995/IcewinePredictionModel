from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, OddsSnapshot, Team
from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore
from icewine_prediction.paper_recommendation_replay_service import (
    build_walk_forward_replay_scorer_factory,
    replay_finished_matches_as_paper_recommendations,
)


def test_replay_finished_matches_records_and_settles_candidates(session):
    league = League(name="Premier Division", country_or_region="Ireland", level=1, is_enabled=True)
    home = Team(canonical_name="Drogheda United")
    away = Team(canonical_name="Waterford")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=1,
        source_name="api_football",
        source_match_id="17446",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=kickoff - timedelta(hours=1),
            data_source="oddspapi",
            bookmaker="pinnacle",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.990"),
            away_odds=Decimal("1.930"),
            total_line=Decimal("2.75"),
            over_odds=Decimal("1.900"),
            under_odds=Decimal("2.000"),
            match_winner_home_odds=Decimal("2.100"),
            match_winner_draw_odds=Decimal("3.250"),
            match_winner_away_odds=Decimal("3.400"),
        )
    )
    session.commit()

    seen_training_cutoffs = []

    def fake_scorer_factory(cutoff):
        seen_training_cutoffs.append(cutoff)

        def score(row):
            assert row["match_id"] == str(match.id)
            return PaperQueueScore(
                side="away_cover",
                model_probability=Decimal("0.6500"),
                market_probability=Decimal("0.5000"),
                edge=Decimal("0.1500"),
                model_name="fake_hgb",
            )

        return score

    result = replay_finished_matches_as_paper_recommendations(
        session,
        from_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        to_time=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer_factory=fake_scorer_factory,
        recorded_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        settle=True,
    )

    assert seen_training_cutoffs == [kickoff]
    assert result.scanned_matches == 1
    assert result.created_records == 1
    assert result.duplicate_records == 0
    assert result.settled_records == 1
    assert len(result.records) == 1
    record = result.records[0]
    assert record.strategy_key == "asian_away_cover_hgb_edge_v1"
    assert record.market_type == "asian_handicap"
    assert record.side == "away_cover"
    assert record.status == "settled"
    assert record.settlement_result == "win"
    assert record.profit_units == Decimal("0.930")
    assert record.is_manually_adjusted is False
    assert record.manual_note is None


def test_replay_finished_matches_skips_duplicate_active_records(session):
    league = League(name="Premier Division", country_or_region="Ireland", level=1, is_enabled=True)
    home = Team(canonical_name="Drogheda United")
    away = Team(canonical_name="Waterford")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=1,
        source_name="api_football",
        source_match_id="17446",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=kickoff - timedelta(hours=1),
            data_source="oddspapi",
            bookmaker="pinnacle",
            asian_handicap=Decimal("-0.50"),
            home_odds=Decimal("1.990"),
            away_odds=Decimal("1.930"),
            total_line=Decimal("2.75"),
            over_odds=Decimal("1.900"),
            under_odds=Decimal("2.000"),
            match_winner_home_odds=Decimal("2.100"),
            match_winner_draw_odds=Decimal("3.250"),
            match_winner_away_odds=Decimal("3.400"),
        )
    )
    session.commit()

    def fake_scorer_factory(cutoff):
        def score(row):
            return PaperQueueScore(
                side="away_cover",
                model_probability=Decimal("0.6500"),
                market_probability=Decimal("0.5000"),
                edge=Decimal("0.1500"),
                model_name="fake_hgb",
            )

        return score

    first = replay_finished_matches_as_paper_recommendations(
        session,
        from_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        to_time=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer_factory=fake_scorer_factory,
        recorded_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        settle=False,
    )
    second = replay_finished_matches_as_paper_recommendations(
        session,
        from_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        to_time=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer_factory=fake_scorer_factory,
        recorded_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        settle=False,
    )

    assert first.created_records == 1
    assert second.created_records == 0
    assert second.duplicate_records == 1


def test_replay_finished_matches_excludes_auxiliary_uefa_matches(session):
    league = League(
        name="UEFA Champions League",
        country_or_region="World",
        level=1,
        is_enabled=True,
        source_league_id="2",
    )
    home = Team(canonical_name="PSG")
    away = Team(canonical_name="Inter")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 31, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=0,
        source_name="api_football",
        source_match_id="uefa-final",
    )
    session.add(match)
    session.commit()

    def fail_if_called(cutoff):
        raise AssertionError("UEFA auxiliary match should not be scored")

    result = replay_finished_matches_as_paper_recommendations(
        session,
        from_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        to_time=datetime(2026, 6, 1, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer_factory=fail_if_called,
        recorded_at=datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        settle=True,
    )

    assert result.scanned_matches == 0


def test_build_walk_forward_replay_scorer_factory_uses_only_rows_before_cutoff(tmp_path, monkeypatch):
    feature_csv = tmp_path / "features.csv"
    feature_csv.write_text(
        "match_id,kickoff_time,target_asian_handicap_away_result,target_total_goals_under_result\n"
        "1,2026-05-29T23:00:00+08:00,win,loss\n"
        "2,2026-05-30T02:45:00+08:00,loss,win\n"
        "3,2026-05-30T04:00:00+08:00,win,win\n",
        encoding="utf-8",
    )
    captured_train_ids = []

    def fake_train_scorer_from_rows(rows):
        captured_train_ids.append([row["match_id"] for row in rows])
        return lambda row: None

    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_replay_service.train_paper_queue_scorer_from_rows",
        fake_train_scorer_from_rows,
    )

    scorer_factory = build_walk_forward_replay_scorer_factory(feature_csv)
    scorer = scorer_factory(datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert scorer({"match_id": "2"}) is None
    assert captured_train_ids == [["1"]]

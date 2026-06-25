from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSnapshot, Team, TrainingRun
from icewine_prediction.paper_strategy_registry import ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueRow,
    PaperQueueScore,
    _apply_execution_robustness_to_rows,
    build_paper_recommendation_queue,
    format_paper_recommendation_queue_report,
    train_paper_queue_scorer_from_rows,
    _team_prior_state,
    _team_prior_states_by_match,
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
            model_probability=Decimal("0.6400"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1400"),
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
    assert candidate.recommended_handicap.endswith("-0.25")


def test_build_paper_recommendation_queue_includes_world_cup_but_excludes_disabled_leagues(session):
    world_cup = League(
        name="FIFA World Cup",
        country_or_region="World",
        level=1,
        is_enabled=True,
        source_league_id="1",
    )
    disabled = League(
        name="Disabled Cup",
        country_or_region="World",
        level=1,
        is_enabled=False,
        source_league_id="9999",
    )
    home = Team(canonical_name="Canada")
    away = Team(canonical_name="Mexico")
    other_home = Team(canonical_name="Disabled Home")
    other_away = Team(canonical_name="Disabled Away")
    session.add_all([world_cup, disabled, home, away, other_home, other_away])
    session.flush()
    now = datetime(2026, 6, 12, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    world_cup_match = Match(
        league=world_cup,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 12, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="world-cup",
    )
    disabled_match = Match(
        league=disabled,
        home_team=other_home,
        away_team=other_away,
        kickoff_time=datetime(2026, 6, 12, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="disabled-cup",
    )
    session.add_all([world_cup_match, disabled_match])
    session.commit()
    seen_match_ids = []

    def no_candidate_scorer(row):
        seen_match_ids.append(row["match_id"])
        return None

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=24,
        scorer=no_candidate_scorer,
    )

    assert report.total_matches == 1
    assert seen_match_ids == [str(world_cup_match.id)]
    assert [row.match_id for row in report.rows] == [world_cup_match.id]
    assert report.rows[0].league_name == "FIFA World Cup"


def test_build_paper_recommendation_queue_uses_latest_successful_training_features(
    session,
    monkeypatch,
):
    older_success = TrainingRun(
        run_type="full_refresh",
        status="success",
        started_at=datetime(2026, 5, 29, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 5, 29, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        snapshot_tag="20260529-0800",
        current_step="finalize",
        dynamic_feature_path="local_data/training/older.csv",
    )
    latest_success = TrainingRun(
        run_type="full_refresh",
        status="success",
        started_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 5, 31, 12, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        snapshot_tag="20260531-1200",
        current_step="finalize",
        dynamic_feature_path="local_data/training/latest.csv",
    )
    failed_later = TrainingRun(
        run_type="full_refresh",
        status="failed",
        started_at=datetime(2026, 5, 31, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 5, 31, 13, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
        snapshot_tag="20260531-1300",
        current_step="dynamic_feature_set",
        dynamic_feature_path="local_data/training/failed.csv",
    )
    session.add_all([older_success, latest_success, failed_later])
    session.commit()
    captured = []

    def fake_train_live_scorer(path):
        captured.append(path)
        return lambda row: None

    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._train_live_scorer",
        fake_train_live_scorer,
    )

    build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=1,
    )

    assert captured == [Path("local_data/training/latest.csv")]


def test_build_paper_recommendation_queue_allows_explicit_feature_path_override(
    session,
    monkeypatch,
):
    session.add(
        TrainingRun(
            run_type="full_refresh",
            status="success",
            started_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            finished_at=datetime(2026, 5, 31, 12, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            snapshot_tag="20260531-1200",
            current_step="finalize",
            dynamic_feature_path="local_data/training/latest.csv",
        )
    )
    session.commit()
    captured = []

    def fake_train_live_scorer(path):
        captured.append(path)
        return lambda row: None

    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._train_live_scorer",
        fake_train_live_scorer,
    )

    build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=1,
        feature_csv_path=Path("local_data/training/manual.csv"),
    )

    assert captured == [Path("local_data/training/manual.csv")]


def test_build_paper_recommendation_queue_reuses_cached_scorer_for_same_feature_file(
    session,
    monkeypatch,
):
    feature_path = Path("local_data/training/latest.csv")
    session.add(
        TrainingRun(
            run_type="full_refresh",
            status="success",
            started_at=datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            finished_at=datetime(2026, 5, 31, 12, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            snapshot_tag="20260531-1200",
            current_step="finalize",
            dynamic_feature_path=str(feature_path),
        )
    )
    session.commit()
    captured = []

    def fake_train_live_scorer(path):
        captured.append(path)
        return lambda row: None

    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._train_live_scorer",
        fake_train_live_scorer,
    )
    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._feature_file_fingerprint",
        lambda path: (path, 123, 456),
    )

    build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=1,
    )
    build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=1,
    )

    assert captured == [feature_path]


def test_train_paper_queue_scorer_passes_numpy_labels_to_calibrated_model(monkeypatch):
    seen_label_arrays = []

    class FakeRawModel:
        def fit(self, matrix, labels):
            return self

        def predict_proba(self, matrix):
            return [[0.60, 0.40]]

        @property
        def named_steps(self):
            return {"classifier": type("Classifier", (), {"classes_": np.asarray(["home_cover", "away_cover"])})()}

    class FakeCalibratedModel:
        classes_ = np.asarray(["home_cover", "away_cover"])

        def fit(self, matrix, labels):
            seen_label_arrays.append(labels)
            assert hasattr(labels, "shape")
            return self

        def predict_proba(self, matrix):
            return [[0.55, 0.45]]

    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._raw_model",
        lambda: FakeRawModel(),
    )
    monkeypatch.setattr(
        "icewine_prediction.paper_recommendation_queue_service._calibrated_model",
        lambda: FakeCalibratedModel(),
    )

    scorer = train_paper_queue_scorer_from_rows(
        [
            _training_row("home_cover", "over"),
            _training_row("away_cover", "under"),
            _training_row("home_cover", "over"),
        ]
    )
    scores = scorer(_training_row("home_cover", "over"))

    assert len(seen_label_arrays) == 2
    assert len(scores) == 3
    hgb_scores = [
        score
        for score in scores
        if score.model_name == "raw_hgb_team_form_plus_all_markets"
    ]
    distribution_scores = [
        score
        for score in scores
        if score.model_name == "poisson_total_goals_distribution"
    ]
    assert len(hgb_scores) == 2
    assert len(distribution_scores) == 1
    assert all(score.calibrated_side is not None for score in hgb_scores)
    assert distribution_scores[0].calibrated_side is None


def test_team_prior_states_by_match_matches_legacy_team_form(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    other_home = Team(canonical_name="Molde")
    other_away = Team(canonical_name="Tromso")
    session.add_all([league, home, away, other_home, other_away])
    session.flush()
    session.add_all(
        [
            Match(
                league=league,
                home_team=home,
                away_team=other_away,
                kickoff_time=datetime(2026, 5, 20, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=2,
                away_score=0,
            ),
            Match(
                league=league,
                home_team=other_home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 21, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=1,
                away_score=1,
            ),
            Match(
                league=league,
                home_team=away,
                away_team=home,
                kickoff_time=datetime(2026, 5, 22, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="finished",
                home_score=0,
                away_score=1,
            ),
        ]
    )
    first = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
    )
    second = Match(
        league=league,
        home_team=away,
        away_team=home,
        kickoff_time=datetime(2026, 5, 31, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
    )
    session.add_all([first, second])
    session.commit()

    states = _team_prior_states_by_match(session, [first, second])

    assert states[(first.id, "home")] == _team_prior_state(first, side="home")
    assert states[(first.id, "away")] == _team_prior_state(first, side="away")
    assert states[(second.id, "home")] == _team_prior_state(second, side="home")
    assert states[(second.id, "away")] == _team_prior_state(second, side="away")


def test_build_paper_recommendation_queue_marks_early_upcoming_odds_not_ready(session):
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
    assert report.rows[0].status == "odds_status_not_ready"


def test_build_paper_recommendation_queue_requires_near_or_close_odds_for_upcoming_matches(session):
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
        kickoff_time=datetime(2026, 5, 30, 6, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="priced-early",
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

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=8,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 0
    assert report.rows[0].status == "odds_status_not_ready"


def test_build_paper_recommendation_queue_allows_near_odds_for_upcoming_matches(session):
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
        kickoff_time=datetime(2026, 5, 30, 2, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="priced-near",
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

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=8,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 1
    assert report.rows[0].status == "candidate"


def test_build_paper_recommendation_queue_does_not_require_close_match_winner_for_finished_matches(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=2,
        source_name="api_football",
        source_match_id="finished-pending-fill",
    )
    session.add(match)
    session.flush()
    for target_minutes in (60, 30, 25, 20, 15, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_time=datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.status == "candidate"
    assert candidate.source_match_id == "finished-pending-fill"
    assert candidate.odds_source == "oddspapi_pinnacle_historical"
    assert candidate.execution_target == "T-10"
    assert candidate.robustness_status == "kept"
    assert candidate.recommended_handicap.endswith("+0.50")


def test_build_paper_recommendation_queue_replays_finished_match_with_historical_close_odds(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=2,
        source_name="api_football",
        source_match_id="finished-priced",
    )
    session.add(match)
    session.flush()
    _add_complete_historical_markets_at_targets(session, match)
    _add_complete_historical_odds(session, match)
    session.commit()

    def fake_scorer(row):
        assert row["asian_handicap_close_line"] == "-0.50"
        assert row["asian_handicap_away_odds"] == "1.930"
        assert row["match_winner_home_implied_probability"] == "0.4762"
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_time=datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer=fake_scorer,
    )

    assert report.total_matches == 1
    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.status == "candidate"
    assert candidate.source_match_id == "finished-priced"
    assert candidate.recommended_handicap.endswith("+0.50")


def test_build_paper_recommendation_queue_replays_finished_match_with_sbobet_historical_odds(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=2,
        source_name="api_football",
        source_match_id="finished-sbobet-priced",
    )
    session.add(match)
    session.flush()
    _add_complete_historical_markets_at_targets(session, match, bookmaker="sbobet")
    _add_complete_historical_odds(session, match, bookmaker="sbobet")
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_time=datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.source_match_id == "finished-sbobet-priced"
    assert candidate.odds_source == "oddspapi_sbobet_historical"


def test_build_paper_recommendation_queue_uses_historical_odds_for_scheduled_match(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-priced",
    )
    session.add(match)
    session.flush()
    _add_complete_historical_markets_at_targets(session, match)
    session.commit()

    def fake_scorer(row):
        assert row["asian_handicap_close_line"] == "-0.50"
        assert row["asian_handicap_away_odds"] == "1.930"
        assert row["match_winner_home_implied_probability"] == "0.4762"
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 50, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=fake_scorer,
    )

    assert report.total_matches == 1
    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.status == "candidate"
    assert candidate.source_match_id == "scheduled-priced"
    assert candidate.odds_source == "oddspapi_pinnacle_historical"
    assert candidate.execution_target == "T-10"
    assert candidate.historical_snapshot_count == 42


def test_paper_queue_prefers_the_odds_api_pinnacle_snapshots_over_oddspapi(session):
    league = League(name="Premier League", country_or_region="England", level=1, is_enabled=True)
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        season=2026,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.flush()
    for source_name, asian_line, home_odds, away_odds in (
        ("oddspapi", Decimal("-0.25"), Decimal("1.90"), Decimal("2.00")),
        ("the_odds_api", Decimal("-0.50"), Decimal("1.80"), Decimal("2.10")),
    ):
        for target_minutes in (60, 30, 25, 20, 15, 10):
            snapshot_time = kickoff - timedelta(minutes=target_minutes)
            _add_source_historical_market_pair(
                session,
                match.id,
                source_name,
                snapshot_time,
                market_type="asian_handicap",
                line=asian_line,
                outcomes={"home": home_odds, "away": away_odds},
            )
            _add_source_historical_market_pair(
                session,
                match.id,
                source_name,
                snapshot_time,
                market_type="total_goals",
                line=Decimal("2.50"),
                outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
            )
            _add_source_historical_market_pair(
                session,
                match.id,
                source_name,
                snapshot_time,
                market_type="match_winner",
                line=Decimal("0.00"),
                outcomes={
                    "home": Decimal("2.10"),
                    "draw": Decimal("3.30"),
                    "away": Decimal("3.40"),
                },
            )
    session.commit()

    seen_rows = []

    def scorer(row):
        seen_rows.append(row)
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.4762"),
            edge=Decimal("0.1738"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        hours=12,
        scorer=scorer,
    )

    candidate = next(row for row in report.rows if row.status == "candidate")
    assert candidate.odds_source == "the_odds_api_pinnacle_historical"
    assert candidate.line == Decimal("-0.50")
    assert seen_rows[0]["asian_handicap_close_line"] == "-0.50"


def test_paper_queue_uses_sbobet_when_pinnacle_is_missing(session):
    league = League(name="Premier League", country_or_region="England", level=1, is_enabled=True)
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        season=2026,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.flush()
    for target_minutes in (60, 30, 25, 20, 15, 10):
        snapshot_time = kickoff - timedelta(minutes=target_minutes)
        _add_source_historical_market_pair(
            session,
            match.id,
            "oddspapi",
            snapshot_time,
            bookmaker="sbobet",
            market_type="asian_handicap",
            line=Decimal("-0.75"),
            outcomes={"home": Decimal("1.91"), "away": Decimal("1.97")},
        )
        _add_source_historical_market_pair(
            session,
            match.id,
            "oddspapi",
            snapshot_time,
            bookmaker="sbobet",
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_source_historical_market_pair(
            session,
            match.id,
            "oddspapi",
            snapshot_time,
            bookmaker="sbobet",
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.30"), "away": Decimal("3.40")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 6, 26, 12, 0, tzinfo=ZoneInfo("UTC")),
        hours=12,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5076"),
            edge=Decimal("0.1424"),
            model_name="fake_hgb",
        ),
    )

    candidate = next(row for row in report.rows if row.status == "candidate")
    assert candidate.odds_source == "oddspapi_sbobet_historical"
    assert candidate.line == Decimal("-0.75")


def test_paper_queue_treats_specific_historical_source_labels_as_historical_for_robustness(session):
    row = PaperQueueRow(
        match_id=1,
        source_match_id="fixture-1",
        kickoff_time="2026-06-26 19:00",
        league_name="Premier League",
        league_display_name="Premier League",
        home_team_name="Arsenal",
        home_team_display_name="Arsenal",
        away_team_name="Chelsea",
        away_team_display_name="Chelsea",
        status="candidate",
        market_type="asian_handicap",
        line=Decimal("-0.75"),
        side="away_cover",
        recommended_handicap="Chelsea +0.75",
        odds=Decimal("1.970"),
        model_probability=Decimal("0.6500"),
        market_probability=Decimal("0.5076"),
        edge=Decimal("0.1424"),
        line_bucket="away_plus",
        risk_tags=(),
        strategy_key=ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
        odds_source="oddspapi_sbobet_historical",
    )
    match = Match(status="scheduled")

    [updated] = _apply_execution_robustness_to_rows(
        [row],
        match=match,
        scorer=lambda _row: None,
        edge_threshold=Decimal("0.0500"),
        display_name_service=None,
        historical_snapshots=[],
        team_prior_states=None,
    )

    assert updated.robustness_status == "unavailable"
    assert "robustness:unavailable" in updated.risk_tags


def test_build_paper_recommendation_queue_ignores_latest_when_t10_targets_are_robust(session):
    league = League(name="T10 Union League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="T10 Home")
    away = Team(canonical_name="T10 Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-t10-union",
    )
    session.add(match)
    session.flush()
    for target_minutes in (60, 30, 25, 20, 15, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    _add_historical_market_pair_at_target(
        session,
        match,
        target_minutes=1,
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        outcomes={"home": Decimal("2.05"), "away": Decimal("1.80")},
    )
    session.commit()
    scorer_calls = []

    def fake_scorer(row):
        scorer_calls.append(row["asian_handicap_away_odds"])
        edge = Decimal("0.0100") if row["asian_handicap_away_odds"] == "1.800" else Decimal("0.1300")
        return PaperQueueScore(
            side="away_cover",
            model_probability=(
                Decimal(row["asian_handicap_away_implied_probability"]) + edge
            ).quantize(Decimal("0.0001")),
            market_probability=Decimal(row["asian_handicap_away_implied_probability"]),
            edge=edge,
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=fake_scorer,
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.status == "candidate"
    assert candidate.execution_target == "T-10"
    assert candidate.odds == Decimal("1.930")
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_primary_target == 10
    assert candidate.robustness_seen_count == 6
    assert candidate.robustness_observed_targets == (10, 15, 20, 25, 30, 60)
    assert report.discarded_by_robustness_match_count == 0
    assert Decimal("1.800") not in [Decimal(value) for value in scorer_calls]
    assert len(scorer_calls) <= 6


def test_build_paper_recommendation_queue_uses_symmetric_timepoint_tolerance(session):
    league = League(name="Symmetric Target League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Symmetric Home")
    away = Team(canonical_name="Symmetric Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-symmetric-target",
    )
    session.add(match)
    session.flush()
    for target_minutes in (60, 25, 20, 15, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    for market_type, line, outcomes in (
        ("asian_handicap", Decimal("-0.50"), {"home": Decimal("2.00"), "away": Decimal("1.90")}),
        ("total_goals", Decimal("2.50"), {"over": Decimal("1.91"), "under": Decimal("1.99")}),
        ("match_winner", Decimal("0.00"), {"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")}),
    ):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=30,
            market_type=market_type,
            line=line,
            outcomes=outcomes,
            offset=timedelta(seconds=12),
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal(row["asian_handicap_away_implied_probability"]),
            edge=Decimal("0.1300"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_seen_count == 6
    assert candidate.robustness_observed_targets == (10, 15, 20, 25, 30, 60)


def test_build_paper_recommendation_queue_sets_scoring_edge_from_trimmed_robust_edges(session):
    league = League(name="Scoring Edge League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Scoring Edge Home")
    away = Team(canonical_name="Scoring Edge Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-scoring-edge",
    )
    session.add(match)
    session.flush()
    away_odds_by_target = {
        60: Decimal("1.810"),
        30: Decimal("1.820"),
        25: Decimal("1.830"),
        20: Decimal("1.840"),
        15: Decimal("1.850"),
        10: Decimal("1.860"),
    }
    edge_by_away_odds = {
        Decimal("1.810"): Decimal("0.0800"),
        Decimal("1.820"): Decimal("0.1100"),
        Decimal("1.830"): Decimal("0.1200"),
        Decimal("1.840"): Decimal("0.1300"),
        Decimal("1.850"): Decimal("0.1400"),
        Decimal("1.860"): Decimal("0.2200"),
    }
    for target_minutes, away_odds in away_odds_by_target.items():
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("2.05"), "away": away_odds},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()

    def fake_scorer(row):
        away_odds = Decimal(row["asian_handicap_away_odds"])
        edge = edge_by_away_odds[away_odds]
        market_probability = Decimal(row["asian_handicap_away_implied_probability"])
        return PaperQueueScore(
            side="away_cover",
            model_probability=(market_probability + edge).quantize(Decimal("0.0001")),
            market_probability=market_probability,
            edge=edge,
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=fake_scorer,
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.execution_target == "T-10"
    assert candidate.edge == Decimal("0.2200")
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_min_edge == Decimal("0.0800")
    assert candidate.scoring_edge == Decimal("0.1250")


def test_build_paper_recommendation_queue_falls_back_to_t30_for_t10_decision_price(session):
    league = League(name="T10 Decision League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Decision Home")
    away = Team(canonical_name="Decision Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-t10-fallback",
    )
    session.add(match)
    session.flush()
    for target_minutes, away_odds in (
        (60, Decimal("1.86")),
        (30, Decimal("1.88")),
        (25, Decimal("1.89")),
        (20, Decimal("1.90")),
        (15, Decimal("1.91")),
    ):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": away_odds},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 50, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal(row["asian_handicap_away_implied_probability"]),
            edge=Decimal("0.1300"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.execution_target == "T-15"
    assert candidate.odds == Decimal("1.910")
    assert candidate.robustness_primary_target == 10
    assert candidate.robustness_seen_count == 5
    assert candidate.robustness_observed_targets == (15, 20, 25, 30, 60)


def test_build_paper_recommendation_queue_does_not_use_t5_or_latest_for_t10_robustness(session):
    league = League(name="No Future Odds League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="No Future Home")
    away = Team(canonical_name="No Future Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-no-future",
    )
    session.add(match)
    session.flush()
    for target_minutes in (25, 20, 15, 10, 5, 1):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 50, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal(row["asian_handicap_away_implied_probability"]),
            edge=Decimal("0.1300"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 0
    assert report.discarded_by_robustness_match_count == 1


def test_build_paper_recommendation_queue_filters_candidate_without_robust_target_support(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-fragile",
    )
    session.add(match)
    session.flush()
    for target_minutes in (15, 5):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 50, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 0
    assert report.rows == []
    assert report.discarded_by_robustness_match_count == 1
    text = format_paper_recommendation_queue_report(report)
    assert "Robustness discarded matches" in text
    assert "| Robustness discarded matches | 1 |" in text


def test_build_paper_recommendation_queue_filters_finished_candidate_like_scheduled(session):
    league = League(name="Finished Fragile League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Finished Fragile Home")
    away = Team(canonical_name="Finished Fragile Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=2,
        source_name="api_football",
        source_match_id="finished-fragile",
    )
    session.add(match)
    session.flush()
    for target_minutes in (15, 5):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    _add_complete_historical_odds(session, match)
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_time=datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 0
    assert report.rows == []
    assert report.discarded_by_robustness_match_count == 1


def test_build_paper_recommendation_queue_reuses_robustness_target_scores_across_strategy_rows(session):
    league = League(name="Norway Eliteserien", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Rosenborg")
    away = Team(canonical_name="Bodo/Glimt")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-multi-signal",
    )
    session.add(match)
    session.flush()
    for target_minutes in (60, 30, 25, 20, 15, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()
    scorer_calls = []

    def fake_scorer(row):
        scorer_calls.append(row["asian_handicap_close_line"])
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.7300"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.2119"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 50, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=fake_scorer,
    )

    assert {row.strategy_key for row in report.rows} == {
        "asian_away_cover_hgb_bucket_v2",
        "asian_away_cover_hgb_edge_v1",
    }
    assert report.candidate_count == 2
    assert len(scorer_calls) == 6


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
    assert report.total_matches == 1
    assert candidate_keys == {
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    }
    v2 = next(row for row in report.rows if row.strategy_key == "asian_away_cover_hgb_bucket_v2")
    assert v2.strategy_display_name == "亚盘客队方向 · HGB分盘口桶 v2"
    assert v2.line_bucket == "away_underdog"
    assert v2.risk_tags == ("line_bucket:away_underdog", "strategy:bucket_v2")


def test_build_paper_recommendation_queue_adds_v2_away_favorite_candidate(session):
    league = League(name="Allsvenskan", country_or_region="Sweden", level=1, is_enabled=True)
    home = Team(canonical_name="Orgryte IS")
    away = Team(canonical_name="IF Elfsborg")
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
        source_match_id="away-favorite",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("0.50"),
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
            model_probability=Decimal("0.6600"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1600"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    v2 = next(row for row in report.rows if row.strategy_key == "asian_away_cover_hgb_bucket_v2")
    assert v2.status == "candidate"
    assert v2.line_bucket == "away_favorite"
    assert v2.recommended_handicap == "客队 -0.50"
    assert v2.risk_tags == ("line_bucket:away_favorite", "strategy:bucket_v2")


def test_build_paper_recommendation_queue_adds_home_favorite_v1_candidate(session):
    league = League(name="Allsvenskan", country_or_region="Sweden", level=1, is_enabled=True)
    home = Team(canonical_name="Malmo FF")
    away = Team(canonical_name="IFK Goteborg")
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
        source_match_id="home-favorite",
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

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            side="home_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        ),
    )

    candidate = next(row for row in report.rows if row.strategy_key == "asian_home_cover_hgb_favorite_bucket_v1")
    assert candidate.status == "candidate"
    assert candidate.market_type == "asian_handicap"
    assert candidate.side == "home_cover"
    assert candidate.line_bucket == "home_favorite"
    assert candidate.recommended_handicap == "主队 -0.50"
    assert candidate.signal_version == "v1"
    assert candidate.risk_tags == (
        "line_bucket:home_favorite",
        "strategy:asian_home_favorite_bucket_v1",
    )
    assert not any(
        row.strategy_key == "asian_away_cover_hgb_edge_v1" and row.side == "home_cover"
        for row in report.rows
    )


def test_build_paper_recommendation_queue_does_not_add_home_favorite_v1_outside_bucket(session):
    league = League(name="Allsvenskan", country_or_region="Sweden", level=1, is_enabled=True)
    home = Team(canonical_name="Malmo FF")
    away = Team(canonical_name="IFK Goteborg")
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
        source_match_id="home-underdog",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            asian_handicap=Decimal("0.50"),
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

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            side="home_cover",
            model_probability=Decimal("0.7000"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2000"),
            model_name="fake_hgb",
        ),
    )

    assert not any(row.strategy_key == "asian_home_cover_hgb_favorite_bucket_v1" for row in report.rows)


def test_build_paper_recommendation_queue_does_not_add_home_favorite_v1_below_threshold(session):
    league = League(name="Allsvenskan", country_or_region="Sweden", level=1, is_enabled=True)
    home = Team(canonical_name="Malmo FF")
    away = Team(canonical_name="IFK Goteborg")
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
        source_match_id="home-favorite-below-threshold",
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

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            side="home_cover",
            model_probability=Decimal("0.6499"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1499"),
            model_name="fake_hgb",
        ),
    )

    assert not any(row.strategy_key == "asian_home_cover_hgb_favorite_bucket_v1" for row in report.rows)


def test_build_paper_recommendation_queue_adds_total_goals_bucket_strategy_candidate(session):
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
        source_match_id="priced-total",
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
        return [
            PaperQueueScore(
                market_type="total_goals",
                side="under",
                model_probability=Decimal("0.5900"),
                market_probability=Decimal("0.5000"),
                edge=Decimal("0.1100"),
                model_name="fake_hgb",
            )
        ]

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    candidate = next(row for row in report.rows if row.strategy_key == "total_goals_hgb_bucket_v2")
    assert candidate.status == "candidate"
    assert candidate.market_type == "total_goals"
    assert candidate.side == "under"
    assert candidate.line == Decimal("2.75")
    assert candidate.odds == Decimal("2.000")
    assert candidate.recommended_handicap.endswith("2.75")
    assert candidate.line_bucket == "mid_2.75"
    assert candidate.risk_tags == ("line_bucket:mid_2.75", "strategy:total_goals_bucket_v2")
    assert [
        row
        for row in report.rows
        if row.status == "candidate"
        and row.market_type == "total_goals"
        and row.strategy_key == "asian_away_cover_hgb_edge_v1"
    ] == []


def test_build_paper_recommendation_queue_does_not_create_hgb_total_goals_from_distribution_score(session):
    match, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.75"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.6127"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1127"),
            model_name="poisson_total_goals_distribution",
        ),
    )

    assert not [
        row
        for row in report.rows
        if row.match_id == match.id
        and row.strategy_key
        in {
            "total_goals_hgb_bucket_v2",
            "total_goals_hgb_low_line_bucket_v3",
            "total_goals_hgb_confirmed_under_low_225_v1",
        }
    ]


def test_build_paper_recommendation_queue_adds_total_goals_low_line_v3_candidate(session):
    match, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.25"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="over",
            model_probability=Decimal("0.5600"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.0600"),
            model_name="fake_hgb",
        ),
    )

    candidate = next(row for row in report.rows if row.strategy_key == "total_goals_hgb_low_line_bucket_v3")
    assert candidate.status == "candidate"
    assert candidate.match_id == match.id
    assert candidate.market_type == "total_goals"
    assert candidate.side == "over"
    assert candidate.line_bucket == "low_<=2.25"
    assert candidate.signal_version == "v3"
    assert candidate.risk_tags == (
        "line_bucket:low_<=2.25",
        "strategy:total_goals_low_line_bucket_v3",
    )


def test_build_paper_recommendation_queue_adds_total_goals_low_line_under_confirmed_candidate(session):
    match, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.25"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.5400"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.0400"),
            model_name="fake_hgb",
            calibrated_side="under",
            calibrated_edge=Decimal("0.0100"),
        ),
    )

    candidate = next(
        row
        for row in report.rows
        if row.strategy_key == "total_goals_hgb_confirmed_under_low_225_v1"
    )
    assert candidate.status == "candidate"
    assert candidate.match_id == match.id
    assert candidate.market_type == "total_goals"
    assert candidate.side == "under"
    assert candidate.line_bucket == "low_<=2.25"
    assert candidate.signal_version == "v1"
    assert candidate.risk_tags == (
        "line_bucket:low_<=2.25",
        "model_consensus:confirmed",
        "strategy:total_goals_hgb_confirmed_under_low_225_v1",
    )


def test_build_paper_recommendation_queue_adds_total_goals_distribution_confirmed_candidates(session):
    _, now = _seed_total_goals_priced_match(session, total_line=Decimal("3.00"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: [
            PaperQueueScore(
                market_type="total_goals",
                side="under",
                model_probability=Decimal("0.6248"),
                market_probability=Decimal("0.5000"),
                edge=Decimal("0.1248"),
                model_name="fake_hgb",
            ),
            PaperQueueScore(
                market_type="total_goals",
                side="under",
                model_probability=Decimal("0.6127"),
                market_probability=Decimal("0.5000"),
                edge=Decimal("0.1127"),
                model_name="poisson_total_goals_distribution",
            ),
        ],
    )

    candidate = next(
        row
        for row in report.rows
        if row.strategy_key == "total_goals_distribution_hgb_confirmed_under_high_300_v1"
    )
    assert candidate.status == "candidate"
    assert candidate.market_type == "total_goals"
    assert candidate.side == "under"
    assert candidate.line_bucket == "high_>=3.00"
    assert candidate.model_probability == Decimal("0.6127")
    assert candidate.edge == Decimal("0.1127")
    assert candidate.risk_tags == (
        "line_bucket:high_>=3.00",
        "strategy:total_goals_distribution_hgb_confirmed_under_high_300_v1",
    )


def test_build_paper_recommendation_queue_applies_robustness_to_distribution_confirmed_candidates(session):
    league = League(name="Distribution Robust League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Distribution Home")
    away = Team(canonical_name="Distribution Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="distribution-robust",
    )
    session.add(match)
    session.flush()
    for target_minutes in (30, 25, 20, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("3.00"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=lambda row: [
            PaperQueueScore(
                market_type="total_goals",
                side="under",
                model_probability=Decimal("0.6248"),
                market_probability=Decimal(row["total_goals_under_implied_probability"]),
                edge=Decimal("0.1248"),
                model_name="fake_hgb",
            ),
            PaperQueueScore(
                market_type="total_goals",
                side="under",
                model_probability=Decimal("0.6127"),
                market_probability=Decimal(row["total_goals_under_implied_probability"]),
                edge=Decimal("0.1127"),
                model_name="poisson_total_goals_distribution",
            ),
        ],
    )

    candidate = next(
        row
        for row in report.rows
        if row.strategy_key == "total_goals_distribution_hgb_confirmed_under_high_300_v1"
    )
    assert candidate.status == "candidate"
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_seen_count == 4
    assert candidate.robustness_observed_targets == (10, 20, 25, 30)


def test_build_paper_recommendation_queue_uses_low_line_v3_side_thresholds(session):
    _, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.25"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.6100"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1100"),
            model_name="fake_hgb",
        ),
    )

    total_rows = [row for row in report.rows if row.market_type == "total_goals"]
    assert total_rows[0].status == "below_threshold"
    assert not any(row.strategy_key == "total_goals_hgb_low_line_bucket_v3" for row in report.rows)


def test_build_paper_recommendation_queue_does_not_add_low_line_v3_outside_low_bucket(session):
    _, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.50"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="over",
            model_probability=Decimal("0.7000"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2000"),
            model_name="fake_hgb",
        ),
    )

    assert not any(row.strategy_key == "total_goals_hgb_low_line_bucket_v3" for row in report.rows)


def test_build_paper_recommendation_queue_keeps_total_goals_candidate_without_asian_odds(session):
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
        source_match_id="priced-total-only",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
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
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.5900"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.0900"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    assert any(row.status == "no_odds" for row in report.rows)
    candidate = next(row for row in report.rows if row.strategy_key == "total_goals_hgb_bucket_v2")
    assert candidate.status == "candidate"
    assert candidate.market_type == "total_goals"


def test_build_paper_recommendation_queue_does_not_candidate_total_goals_outside_bucket(session):
    league = League(name="Allsvenskan", country_or_region="Sweden", level=1, is_enabled=True)
    home = Team(canonical_name="Mjallby AIF")
    away = Team(canonical_name="Djurgardens IF")
    session.add_all([league, home, away])
    session.flush()
    now = datetime(2026, 5, 31, 20, 39, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 31, 22, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="1494190",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            total_line=Decimal("2.50"),
            over_odds=Decimal("1.78"),
            under_odds=Decimal("1.98"),
            match_winner_home_odds=Decimal("2.40"),
            match_winner_draw_odds=Decimal("3.25"),
            match_winner_away_odds=Decimal("2.70"),
        )
    )
    session.commit()

    def fake_scorer(row):
        return PaperQueueScore(
            market_type="total_goals",
            side="over",
            model_probability=Decimal("0.6593"),
            market_probability=Decimal("0.5266"),
            edge=Decimal("0.1327"),
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=fake_scorer,
    )

    total_rows = [row for row in report.rows if row.market_type == "total_goals"]
    assert len(total_rows) == 1
    assert total_rows[0].line == Decimal("2.50")
    assert total_rows[0].line_bucket == "mid_2.50"
    assert total_rows[0].status == "unsupported_bucket"
    assert not any(row.strategy_key == "total_goals_hgb_bucket_v2" for row in report.rows)
    assert report.candidate_count == 0


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


def _seed_total_goals_priced_match(
    session,
    *,
    total_line: Decimal,
) -> tuple[Match, datetime]:
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
        source_match_id=f"priced-total-{total_line}",
    )
    session.add(match)
    session.flush()
    session.add(
        OddsSnapshot(
            match=match,
            captured_at=now,
            data_source="api_football",
            bookmaker="Bet365",
            total_line=total_line,
            over_odds=Decimal("1.90"),
            under_odds=Decimal("2.00"),
            match_winner_home_odds=Decimal("2.10"),
            match_winner_draw_odds=Decimal("3.25"),
            match_winner_away_odds=Decimal("3.40"),
        )
    )
    session.commit()
    return match, now


def _training_row(asian_actual_side: str, total_actual_side: str) -> dict[str, str]:
    row = {
        "match_id": "1",
        "source_match_id": "1",
        "league_name": "League",
        "league_source_id": "1",
        "season": "2026",
        "kickoff_time": "2026-01-01T12:00:00+08:00",
        "split": "train",
        "home_team_name": "Home",
        "away_team_name": "Away",
        "target_match_result": "home",
        "target_home_score": "2",
        "target_away_score": "1",
        "target_total_goals": "3",
        "target_asian_handicap_home_result": "win" if asian_actual_side == "home_cover" else "loss",
        "target_asian_handicap_away_result": "loss" if asian_actual_side == "home_cover" else "win",
        "asian_handicap_close_line": "-0.50",
        "asian_handicap_home_odds": "1.950",
        "asian_handicap_away_odds": "1.950",
        "total_goals_close_line": "2.75",
        "target_total_goals_over_result": "win" if total_actual_side == "over" else "loss",
        "target_total_goals_under_result": "loss" if total_actual_side == "over" else "win",
        "total_goals_over_odds": "1.900",
        "total_goals_under_odds": "2.000",
        "match_winner_home_implied_probability": "0.4762",
        "match_winner_draw_implied_probability": "0.3077",
        "match_winner_away_implied_probability": "0.2941",
        "match_winner_overround": "1.0780",
        "asian_handicap_home_implied_probability": "0.5000",
        "asian_handicap_away_implied_probability": "0.5000",
        "asian_handicap_overround": "1.0000",
        "total_goals_over_implied_probability": "0.5000",
        "total_goals_under_implied_probability": "0.5000",
        "total_goals_overround": "1.0000",
        "quality_tags": "",
    }
    for prefix in ("home", "away"):
        row.update(
            {
                f"{prefix}_prior_matches": "10",
                f"{prefix}_prior_points_per_match": "1.5000",
                f"{prefix}_prior_win_rate": "0.4000",
                f"{prefix}_prior_draw_rate": "0.3000",
                f"{prefix}_prior_loss_rate": "0.3000",
                f"{prefix}_prior_goals_for_per_match": "1.4000",
                f"{prefix}_prior_goals_against_per_match": "1.2000",
                f"{prefix}_prior_{'home' if prefix == 'home' else 'away'}_matches": "5",
                f"{prefix}_prior_{'home' if prefix == 'home' else 'away'}_points_per_match": "1.6000",
                f"{prefix}_rest_days": "7.00",
            }
        )
    return row


def _add_historical_market_pair(
    session,
    match: Match,
    *,
    market_type: str,
    line: Decimal,
    outcomes: dict[str, Decimal],
) -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=30)
    for side, odds in outcomes.items():
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker="pinnacle",
                market_type=market_type,
                market_id=f"{market_type}-{side}",
                market_name=market_type,
                market_line=line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )


def _add_source_historical_market_pair(
    session,
    match_id: int,
    source_name: str,
    snapshot_time: datetime,
    *,
    bookmaker: str = "pinnacle",
    market_type: str,
    line: Decimal,
    outcomes: dict[str, Decimal],
) -> None:
    session.add_all(
        [
            HistoricalOddsSnapshot(
                match_id=match_id,
                source_name=source_name,
                source_fixture_id=f"{source_name}-event",
                bookmaker=bookmaker,
                market_type=market_type,
                market_id=f"{source_name}:{market_type}:{snapshot_time.isoformat()}:{side}",
                market_name=market_type,
                market_line=line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="full_time",
            )
            for side, odds in outcomes.items()
        ]
    )


def _add_historical_market_pair_at_target(
    session,
    match: Match,
    *,
    target_minutes: int,
    market_type: str,
    line: Decimal,
    outcomes: dict[str, Decimal],
    offset: timedelta = timedelta(0),
    bookmaker: str = "pinnacle",
) -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=target_minutes) + offset
    for side, odds in outcomes.items():
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker=bookmaker,
                market_type=market_type,
                market_id=f"{market_type}-{target_minutes}-{side}",
                market_name=market_type,
                market_line=line,
                outcome_side=side,
                odds=odds,
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )


def _add_complete_historical_markets_at_targets(
    session,
    match: Match,
    *,
    bookmaker: str = "pinnacle",
) -> None:
    for target_minutes in (60, 30, 25, 20, 15, 10):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
            bookmaker=bookmaker,
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
            bookmaker=bookmaker,
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
            bookmaker=bookmaker,
        )


def _add_complete_historical_odds(session, match: Match, *, bookmaker: str = "pinnacle") -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=6)
    markets = [
        ("asian_handicap", Decimal("-0.50"), ("home", "away"), {"home": Decimal("1.99"), "away": Decimal("1.93")}),
        ("total_goals", Decimal("2.50"), ("over", "under"), {"over": Decimal("1.90"), "under": Decimal("2.00")}),
        (
            "match_winner",
            Decimal("0.00"),
            ("home", "draw", "away"),
            {"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        ),
    ]
    counts = {market_type: 0 for market_type, _, _, _ in markets}
    for index in range(120):
        market_type, line, sides, odds_by_side = markets[index % len(markets)]
        side = sides[counts[market_type] % len(sides)]
        counts[market_type] += 1
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker=bookmaker,
                market_type=market_type,
                market_id=f"complete-{market_type}-{index}",
                market_name=market_type,
                market_line=line,
                outcome_side=side,
                odds=odds_by_side[side],
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )

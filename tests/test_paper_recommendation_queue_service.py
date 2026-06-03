from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from icewine_prediction.execution_robustness_rules import DEFAULT_SELECTED_ROBUSTNESS_RULES
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSnapshot, Team, TrainingRun
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueScore,
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
    assert len(scores) == 2
    assert all(score.calibrated_side is not None for score in scores)


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


def test_build_paper_recommendation_queue_requires_filled_odds_for_finished_matches(session):
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
    _add_historical_market_pair(
        session,
        match,
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="total_goals",
        line=Decimal("2.50"),
        outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="match_winner",
        line=Decimal("0.00"),
        outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
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

    assert report.candidate_count == 0
    assert report.rows[0].status == "odds_status_not_ready"


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
    _add_historical_market_pair(
        session,
        match,
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="total_goals",
        line=Decimal("2.50"),
        outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="match_winner",
        line=Decimal("0.00"),
        outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
    )
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
    _add_historical_market_pair(
        session,
        match,
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="total_goals",
        line=Decimal("2.50"),
        outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
    )
    _add_historical_market_pair(
        session,
        match,
        market_type="match_winner",
        line=Decimal("0.00"),
        outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
    )
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
    assert candidate.odds_source == "oddspapi_historical"
    assert candidate.execution_target == "latest_historical"
    assert candidate.historical_snapshot_count == 7


def test_confirmed_under_mid_275_uses_filter_mode():
    rule = DEFAULT_SELECTED_ROBUSTNESS_RULES["total_goals_hgb_confirmed_under_mid_275_v1"]

    assert rule.mode == "filter"


def test_build_paper_recommendation_queue_discovers_latest_only_candidate_when_fixed_targets_are_robust(session):
    league = League(name="Latest Union League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Latest Home")
    away = Team(canonical_name="Latest Away")
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
        source_match_id="scheduled-latest-union",
    )
    session.add(match)
    session.flush()
    for target_minutes in (25, 20, 15, 10, 5):
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
        edge = Decimal("0.1300") if row["asian_handicap_away_odds"] == "1.800" else Decimal("0.0900")
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
    assert candidate.execution_target == "T-15"
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_seen_count == 5
    assert candidate.robustness_observed_targets == (5, 10, 15, 20, 25)
    assert report.discarded_by_robustness_match_count == 0
    assert len(scorer_calls) <= 6


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
    row = report.rows[0]
    assert row.status == "robustness_filtered"
    assert "robustness:filtered" in row.risk_tags
    assert row.robustness_mode == "filter"
    assert row.robustness_status == "filtered"
    assert row.robustness_primary_target == 15
    assert row.robustness_seen_count == 4
    assert row.robustness_min_edge == Decimal("0.1319")
    assert row.robustness_observed_targets == (5, 10, 15, 20)


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
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    }
    assert report.candidate_count == 1
    assert len(scorer_calls) == 5


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


def test_build_paper_recommendation_queue_adds_total_goals_confirmed_under_mid_275_candidate(session):
    match, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.75"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
            calibrated_side="under",
            calibrated_edge=Decimal("0.0100"),
        ),
    )

    candidate = next(
        row
        for row in report.rows
        if row.strategy_key == "total_goals_hgb_confirmed_under_mid_275_v1"
    )
    assert candidate.status == "candidate"
    assert candidate.match_id == match.id
    assert candidate.market_type == "total_goals"
    assert candidate.side == "under"
    assert candidate.line_bucket == "mid_2.75"
    assert candidate.signal_version == "v1"
    assert candidate.risk_tags == (
        "line_bucket:mid_2.75",
        "model_consensus:confirmed",
        "strategy:total_goals_confirmed_under_mid_275_v1",
    )


def test_build_paper_recommendation_queue_does_not_add_confirmed_under_mid_275_when_calibrated_diverges(session):
    _, now = _seed_total_goals_priced_match(session, total_line=Decimal("2.75"))

    report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=6,
        scorer=lambda row: PaperQueueScore(
            market_type="total_goals",
            side="under",
            model_probability=Decimal("0.6600"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1600"),
            model_name="fake_hgb",
            calibrated_side="over",
            calibrated_edge=Decimal("-0.0200"),
        ),
    )

    assert not any(
        row.strategy_key == "total_goals_hgb_confirmed_under_mid_275_v1"
        for row in report.rows
    )


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


def _add_historical_market_pair_at_target(
    session,
    match: Match,
    *,
    target_minutes: int,
    market_type: str,
    line: Decimal,
    outcomes: dict[str, Decimal],
) -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=target_minutes)
    for side, odds in outcomes.items():
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker="pinnacle",
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


def _add_complete_historical_odds(session, match: Match) -> None:
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
                bookmaker="pinnacle",
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

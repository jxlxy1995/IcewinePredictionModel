from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.display_service import DisplayNameService, DisplayNames, load_display_names
from icewine_prediction.display_translation_status_service import DisplayTranslationStatusService
from icewine_prediction.models import (
    DataSyncRunItem,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    OddsSnapshot,
    RecommendationRecord,
    Team,
    TrainingRun,
)
from icewine_prediction.sources.api_football_mapper import ExternalOddsSnapshot
from icewine_prediction import web_api
from icewine_prediction.web_api import create_web_app


def test_web_console_api_returns_dashboard_summary(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matches"] == 2
    assert payload["finished_matches"] == 2
    assert payload["matches_with_historical_odds"] == 1
    assert payload["unmatched_matches"] == 1
    assert payload["historical_odds_snapshots"] == 5


def test_web_console_api_caches_dashboard_summary_until_ttl_expires(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    first_response = client.get("/api/dashboard/summary")
    with session_factory() as session:
        league = session.query(League).one()
        home = session.query(Team).filter(Team.canonical_name == "Cardiff").one()
        away = session.query(Team).filter(Team.canonical_name == "Swansea").one()
        session.add(
            Match(
                league_id=league.id,
                home_team_id=home.id,
                away_team_id=away.id,
                kickoff_time=datetime(2026, 5, 22, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                season=2025,
                status="finished",
            )
        )
        session.commit()
    second_response = client.get("/api/dashboard/summary")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["total_matches"] == 2
    assert second_response.json()["total_matches"] == 2


def test_web_console_api_returns_league_coverage(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/leagues/coverage")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["league_id"] == 1
    assert payload[0]["league_name"] == "英冠"
    assert payload[0]["league_display_name"] == "英冠"
    assert payload[0]["country_or_region"] == "England"
    assert payload[0]["coverage_ratio"] == "0.5000"


def test_web_console_api_returns_worker_statuses(tmp_path):
    worker_status_dir = tmp_path / "workers"
    worker_status_dir.mkdir()
    (worker_status_dir / "1234.json").write_text(
        """
        {
          "pid": 1234,
          "started_at": "2026-05-25T21:04:22+08:00",
          "status": "started",
          "mode": "balanced",
          "season": 2025,
          "league_ids": ["39", "40"],
          "process_log_path": "logs/odds/process.log",
          "worker_log_dir": "logs/odds",
          "notify_on_complete": true
        }
        """,
        encoding="utf-8",
    )

    client = TestClient(
        create_web_app(
            log_dir=tmp_path,
            process_running_checker=lambda pid: pid == 1234,
        )
    )

    response = client.get("/api/workers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "pid": 1234,
            "started_at": "2026-05-25T21:04:22+08:00",
            "status": "started",
            "runtime_status": "running",
            "mode": "balanced",
            "season": 2025,
            "league_ids": ["39", "40"],
            "process_log_path": "logs/odds/process.log",
            "worker_log_dir": "logs/odds",
            "notify_on_complete": True,
        }
    ]


def test_web_console_api_returns_oddspapi_backfill_audit(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    (tmp_path / "oddspapi-worker-progress.json").write_text(
        """
        {
          "status": "running",
          "mode": "balanced",
          "season": 2025,
          "updated_at": "2026-05-27T10:15:00+08:00",
          "current_league": {
            "league_id": "40",
            "league_name": "Championship",
            "round": 12,
            "processed_matches": 18,
            "inserted_snapshots": 540,
            "failed_matches": 2,
            "requests_used": 31
          },
          "totals": {
            "processed_matches": 180,
            "inserted_snapshots": 5400,
            "failed_matches": 12,
            "requests_used": 310
          }
        }
        """,
        encoding="utf-8",
    )

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/oddspapi/backfill-audit?season=2025")

    assert response.status_code == 200
    payload = response.json()
    assert payload["season"] == 2025
    assert payload["worker_progress"] == {
        "status": "running",
        "mode": "balanced",
        "season": 2025,
        "updated_at": "2026-05-27T10:15:00+08:00",
        "current_league_id": "40",
        "current_league_name": "Championship",
        "current_league_display_name": "英冠",
        "round": 12,
        "processed_matches": 18,
        "inserted_snapshots": 540,
        "failed_matches": 2,
        "requests_used": 31,
        "total_processed_matches": 180,
        "total_inserted_snapshots": 5400,
        "total_failed_matches": 12,
        "total_requests_used": 310,
    }
    assert len(payload["league_summaries"]) == 1
    league_summary = payload["league_summaries"][0]
    assert league_summary["league_name"]
    assert league_summary["league_display_name"]
    assert league_summary["source_league_id"] == "40"
    assert league_summary["finished_matches"] == 2
    assert league_summary["matched_matches"] == 0
    assert league_summary["snapshot_matches"] == 1
    assert league_summary["snapshot_count"] == 5
    assert league_summary["asian_handicap_snapshot_count"] == 1
    assert league_summary["total_goals_snapshot_count"] == 1
    assert league_summary["status_counts"] == {"unmatched": 1}
    assert league_summary["error_counts"] == {}


def test_web_console_api_returns_unmatched_matches(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/unmatched")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["league_name"] == "英冠"
    assert payload[0]["home_team_name"] == "Wolves"
    assert payload[0]["away_team_name"] == "Leeds"
    assert payload[0]["source_name"] == "oddspapi"
    assert payload[0]["match_reason"] == "未匹配到 OddsPapi 比赛"


def test_web_console_api_returns_match_odds_trends(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get(f"/api/matches/{seeded['matched_match_id']}/odds-trends")

    assert response.status_code == 200
    payload = response.json()
    assert payload["match_id"] == seeded["matched_match_id"]
    assert payload["league_name"] == "英冠"
    assert payload["home_team_name"] == "Cardiff"
    assert payload["away_team_name"] == "Swansea"
    assert payload["asian_handicap"][0]["snapshot_time"] == "2026-05-20T20:00:00+08:00"
    assert payload["asian_handicap"][0]["market_line"] == "-0.25"
    assert payload["asian_handicap"][0]["home_odds"] == "1.930"
    assert payload["total_goals"][0]["market_line"] == "2.50"
    assert payload["total_goals"][0]["over_odds"] == "1.910"
    assert payload["match_winner"][0]["market_line"] == "0.00"
    assert payload["match_winner"][0]["home_odds"] == "2.100"
    assert payload["match_winner"][0]["draw_odds"] == "3.250"
    assert payload["match_winner"][0]["away_odds"] == "3.400"


def test_web_console_api_returns_display_names_without_replacing_raw_names(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)
    display_name_service = DisplayNameService(
        DisplayNames(
            leagues={"英冠": "英冠"},
            teams={
                "Cardiff": "卡迪夫城",
                "Swansea": "斯旺西",
                "Wolves": "狼队",
                "Leeds": "利兹联",
            },
        )
    )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=display_name_service,
        )
    )

    response = client.get(f"/api/matches/{seeded['matched_match_id']}/odds-trends")

    assert response.status_code == 200
    payload = response.json()
    assert payload["home_team_name"] == "Cardiff"
    assert payload["away_team_name"] == "Swansea"
    assert payload["home_team_display_name"] == "卡迪夫城"
    assert payload["away_team_display_name"] == "斯旺西"


def test_web_console_api_returns_missing_team_display_names(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    display_name_service = DisplayNameService(
        DisplayNames(
            leagues={"英冠": "英冠"},
            teams={
                "Cardiff": "卡迪夫城",
                "Swansea": "斯旺西",
                "Leeds": "利兹联",
            },
        )
    )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=display_name_service,
        )
    )

    response = client.get("/api/display/missing-team-names")

    assert response.status_code == 200
    assert response.json() == [
        {
            "league_id": 1,
            "league_name": "英冠",
            "league_display_name": "英冠",
            "season": 2025,
            "team_id": 3,
            "team_name": "Wolves",
            "team_display_name": None,
            "team_logo_url": "https://media.api-sports.io/football/teams/wolves.png",
            "is_missing_display_name": True,
            "match_count": 1,
            "latest_kickoff_time": "2026-05-21T22:00:00",
            "rank": None,
            "points": None,
        }
    ]


def test_web_console_api_returns_team_display_name_workspace(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    display_name_service = DisplayNameService(
        DisplayNames(
            leagues={"英冠": "英冠"},
            teams={
                "Cardiff": "卡迪夫城",
                "Swansea": "斯旺西",
                "Leeds": "利兹联",
            },
        )
    )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=display_name_service,
            display_translation_status_service=DisplayTranslationStatusService(
                tmp_path / "display_translation_status.yaml"
            ),
        )
    )

    response = client.get("/api/display/team-name-workspace?league_id=1&season=2025")

    assert response.status_code == 200
    payload = response.json()
    assert payload["league_id"] == 1
    assert payload["league_display_name"] == "英冠"
    assert payload["season"] == 2025
    assert payload["is_translation_done"] is False
    assert payload["teams"] == [
        {
            "league_id": 1,
            "league_name": "英冠",
            "league_display_name": "英冠",
            "season": 2025,
            "team_id": 1,
            "team_name": "Cardiff",
            "team_display_name": "卡迪夫城",
            "team_logo_url": None,
            "is_missing_display_name": False,
            "match_count": 1,
            "latest_kickoff_time": "2026-05-20T22:00:00",
            "rank": None,
            "points": None,
        },
        {
            "league_id": 1,
            "league_name": "英冠",
            "league_display_name": "英冠",
            "season": 2025,
            "team_id": 4,
            "team_name": "Leeds",
            "team_display_name": "利兹联",
            "team_logo_url": None,
            "is_missing_display_name": False,
            "match_count": 1,
            "latest_kickoff_time": "2026-05-21T22:00:00",
            "rank": None,
            "points": None,
        },
        {
            "league_id": 1,
            "league_name": "英冠",
            "league_display_name": "英冠",
            "season": 2025,
            "team_id": 2,
            "team_name": "Swansea",
            "team_display_name": "斯旺西",
            "team_logo_url": None,
            "is_missing_display_name": False,
            "match_count": 1,
            "latest_kickoff_time": "2026-05-20T22:00:00",
            "rank": None,
            "points": None,
        },
        {
            "league_id": 1,
            "league_name": "英冠",
            "league_display_name": "英冠",
            "season": 2025,
            "team_id": 3,
            "team_name": "Wolves",
            "team_display_name": None,
            "team_logo_url": "https://media.api-sports.io/football/teams/wolves.png",
            "is_missing_display_name": True,
            "match_count": 1,
            "latest_kickoff_time": "2026-05-21T22:00:00",
            "rank": None,
            "points": None,
        },
    ]


def test_web_console_api_marks_team_display_name_workspace_done(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    _seed_console_data(session_factory)
    status_service = DisplayTranslationStatusService(tmp_path / "display_translation_status.yaml")

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_translation_status_service=status_service,
        )
    )

    response = client.post("/api/display/team-name-workspace/done", json={"league_id": 1, "season": 2025})

    assert response.status_code == 200
    assert response.json() == {"league_id": 1, "season": 2025, "is_translation_done": True}
    assert status_service.is_done(league_id=1, season=2025) is True


def test_web_console_api_saves_team_display_names(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    display_names_path = tmp_path / "display_names.yaml"
    display_names_path.write_text("leagues:\n  英冠: 英冠\nteams: {}\n", encoding="utf-8")

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_names_path=display_names_path,
        )
    )

    response = client.post(
        "/api/display/team-names",
        json={"teams": {"Wolves": "狼队", "Cardiff": "卡迪夫城"}},
    )

    assert response.status_code == 200
    assert response.json() == {"saved_count": 2}
    display_name_service = DisplayNameService(load_display_names(display_names_path))
    assert display_name_service.display_team("Wolves") == "狼队"
    assert display_name_service.display_team("Cardiff") == "卡迪夫城"


def test_web_console_api_returns_matches_with_odds(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/matches/with-odds")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["match_id"] == seeded["matched_match_id"]
    assert payload[0]["league_name"] == "英冠"
    assert payload[0]["league_display_name"] == "英冠"
    assert payload[0]["home_team_name"] == "Cardiff"
    assert payload[0]["home_team_display_name"] == "卡迪夫城"
    assert payload[0]["away_team_name"] == "Swansea"
    assert payload[0]["away_team_display_name"] == "斯旺西"
    assert payload[0]["snapshot_count"] == 5


def test_web_console_api_returns_recommendation_records(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))

    response = client.get("/api/recommendation-records")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == 1
    assert payload[0]["match_id"] == seeded["matched_match_id"]
    assert payload[0]["home_team_name"] == "Cardiff"
    assert payload[0]["home_team_display_name"] == "卡迪夫城"
    assert payload[0]["home_team_logo_url"] is None
    assert payload[0]["away_team_name"] == "Swansea"
    assert payload[0]["away_team_display_name"] == "斯旺西"
    assert payload[0]["away_team_logo_url"] is None
    assert payload[0]["home_score"] == 2
    assert payload[0]["away_score"] == 1
    assert payload[0]["market_type"] == "asian_handicap"
    assert payload[0]["confidence_grade"] == "A-"


def test_web_console_api_returns_paper_recommendation_queue(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)

    with session_factory() as session:
        match = session.get(Match, seeded["matched_match_id"])
        match.status = "scheduled"
        match.kickoff_time = datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        session.add(
            OddsSnapshot(
                match_id=match.id,
                captured_at=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Bet365",
                asian_handicap=Decimal("0.25"),
                home_odds=Decimal("1.95"),
                away_odds=Decimal("1.95"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.90"),
                under_odds=Decimal("2.00"),
            )
        )
        session.commit()

    def fake_scorer(row):
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=DisplayNameService(
                DisplayNames(
                    leagues={"鑻卞啝": "Test League", "英冠": "Test League"},
                    teams={"Cardiff": "Test Home", "Swansea": "Test Away"},
                )
            ),
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.get("/api/paper-recommendations/queue?hours=6&near_start_hours=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matches"] >= 1
    assert payload["candidate_count"] >= 1
    candidate = next(row for row in payload["rows"] if row["status"] == "candidate")
    assert candidate["league_display_name"] == "Test League"
    assert candidate["home_team_display_name"] == "Test Home"
    assert candidate["recommended_handicap"].endswith("-0.25")

def test_web_console_api_paper_workspace_replays_finished_window(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)

    with session_factory() as session:
        match = session.get(Match, seeded["matched_match_id"])
        match.kickoff_time = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id="p1",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="ah-away",
                market_name="Asian Handicap",
                market_line=Decimal("-0.50"),
                outcome_side="away",
                odds=Decimal("1.930"),
                snapshot_time=datetime(2026, 5, 29, 18, 30, tzinfo=ZoneInfo("UTC")),
                period="prematch",
            )
        )
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id="p1",
                bookmaker="pinnacle",
                market_type="total_goals",
                market_id="ou-under",
                market_name="Total Goals",
                market_line=Decimal("2.50"),
                outcome_side="under",
                odds=Decimal("2.000"),
                snapshot_time=datetime(2026, 5, 29, 18, 30, tzinfo=ZoneInfo("UTC")),
                period="prematch",
            )
        )
        _add_complete_historical_odds(session, match)
        session.commit()

    def fake_scorer(row):
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        assert row["asian_handicap_away_odds"] == "1.930"
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.get(
        "/api/paper-recommendations/workspace"
        "?start_time=2026-05-30T00:00:00%2B08:00"
        "&end_time=2026-05-30T23:59:00%2B08:00"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["match_id"] == seeded["matched_match_id"]

def test_web_console_api_paper_tracking_workspace_and_record_flow(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United", logo_url="https://img.example/home.png")
        away = Team(canonical_name="Waterford", logo_url="https://img.example/away.png")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 30, 2, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
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
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=DisplayNameService(
                DisplayNames(
                    leagues={"Premier Division": "爱超"},
                    teams={"Drogheda United": "德罗赫达联", "Waterford": "沃特福德联"},
                )
            ),
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    workspace_response = client.get("/api/paper-recommendations/workspace?hours=6")
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()
    assert workspace["summary"]["candidate_count"] == 1
    assert workspace["diagnostics"] == {
        "total_matches": 1,
        "candidate_count": 1,
        "candidate_match_count": 1,
        "status_counts": {"candidate": 1},
        "edge_threshold": "0.1000",
    }
    assert workspace["candidates"][0]["recommended_handicap"] == "客队 +0.50"
    assert workspace["strategies"][0]["display_name"] == "亚盘客队方向 · HGB边际 v1"

    create_response = client.post(
        "/api/paper-recommendations/records",
        json={"match_id": match.id},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["strategy_display_name"] == "亚盘客队方向 · HGB边际 v1"
    assert created["recommended_handicap"] == "客队 +0.50"
    assert created["current_market_line"] == "-0.50"
    assert created["current_odds"] == "1.930"

    edit_response = client.patch(
        f"/api/paper-recommendations/records/{created['id']}",
        json={
            "current_market_line": "-0.25",
            "current_odds": "1.880",
            "manual_note": "临场退盘，按人工确认盘口观察",
        },
    )
    assert edit_response.status_code == 200
    edited = edit_response.json()
    assert edited["original_market_line"] == "-0.50"
    assert edited["current_market_line"] == "-0.25"
    assert edited["recommended_handicap"] == "客队 +0.25"
    assert edited["is_manually_adjusted"] is True

    with session_factory() as session:
        db_match = session.get(Match, match.id)
        db_match.status = "finished"
        db_match.home_score = 1
        db_match.away_score = 1
        session.commit()

    settle_response = client.post("/api/paper-recommendations/settle")
    assert settle_response.status_code == 200
    assert settle_response.json()["settled_count"] == 1

    settled_workspace = client.get("/api/paper-recommendations/workspace?hours=6").json()
    assert settled_workspace["summary"]["settled_records"] == 1
    assert settled_workspace["summary"]["roi"] == "0.4400"
    assert settled_workspace["records"][0]["settlement_result"] == "half_win"
    assert settled_workspace["records"][0]["profit_units"] == "0.440"
    assert settled_workspace["records"][0]["home_team_logo_url"] == "https://img.example/home.png"
    assert settled_workspace["records"][0]["away_team_logo_url"] == "https://img.example/away.png"
    assert settled_workspace["records"][0]["home_score"] == 1
    assert settled_workspace["records"][0]["away_score"] == 1


def test_web_console_api_voids_paper_record(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United", logo_url="https://img.example/home.png")
        away = Team(canonical_name="Waterford", logo_url="https://img.example/away.png")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.commit()

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))
    from icewine_prediction.paper_recommendation_tracking_service import create_paper_record_from_queue_row
    from tests.test_paper_recommendation_tracking_service import _queue_row

    with session_factory() as session:
        match = session.query(Match).one()
        record = create_paper_record_from_queue_row(
            session,
            _queue_row(match, status="candidate", line=Decimal("-0.50")),
            recorded_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        record_id = record.id

    response = client.post(f"/api/paper-recommendations/records/{record_id}/void")

    assert response.status_code == 200
    assert response.json()["status"] == "void"


def test_web_console_api_paper_workspace_lists_only_recordable_candidates(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United")
        away = Team(canonical_name="Waterford")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 29, 23, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
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
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    workspace_response = client.get("/api/paper-recommendations/workspace?hours=6")
    queue_response = client.get("/api/paper-recommendations/queue?hours=6")

    assert workspace_response.status_code == 200
    assert queue_response.status_code == 200
    workspace = workspace_response.json()
    queue = queue_response.json()
    assert queue["rows"][0]["status"] == "odds_status_not_ready"
    assert workspace["summary"]["candidate_count"] == 0
    assert workspace["candidates"] == []


def test_web_console_api_records_v2_paper_candidate_by_strategy_key(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United")
        away = Team(canonical_name="Waterford")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
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
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.7100"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2100"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    workspace = client.get("/api/paper-recommendations/workspace?hours=6").json()
    assert {strategy["strategy_key"] for strategy in workspace["strategies"]} == {
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
        "asian_home_cover_hgb_favorite_bucket_v1",
        "total_goals_hgb_bucket_v2",
        "total_goals_hgb_low_line_bucket_v3",
        "total_goals_hgb_confirmed_under_mid_275_v1",
    }
    assert {candidate["strategy_key"] for candidate in workspace["candidates"]} == {
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    }
    v2_candidate = next(
        candidate
        for candidate in workspace["candidates"]
        if candidate["strategy_key"] == "asian_away_cover_hgb_bucket_v2"
    )
    assert v2_candidate["signal_version"] == "v2"

    response = client.post(
        "/api/paper-recommendations/records",
        json={"match_id": match.id, "strategy_key": "asian_away_cover_hgb_bucket_v2"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_key"] == "asian_away_cover_hgb_bucket_v2"
    assert payload["strategy_display_name"] == "亚盘客队方向 · HGB分盘口桶 v2"
    assert payload["signal_version"] == "v2"


def test_web_console_api_batch_records_paper_candidates_with_single_queue_build(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United", logo_url="https://img.example/home.png")
        away = Team(canonical_name="Waterford", logo_url="https://img.example/away.png")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.90"),
                under_odds=Decimal("2.00"),
                match_winner_home_odds=Decimal("2.10"),
                match_winner_draw_odds=Decimal("3.25"),
                match_winner_away_odds=Decimal("3.40"),
            )
        )
        session.commit()

    scorer_calls = []

    def fake_scorer(row):
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        scorer_calls.append(row["match_id"])
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.7100"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2100"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.post(
        "/api/paper-recommendations/records/batch",
        json={
            "candidates": [
                {"match_id": match.id, "strategy_key": "asian_away_cover_hgb_edge_v1"},
                {"match_id": match.id, "strategy_key": "asian_away_cover_hgb_bucket_v2"},
            ],
            "hours": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [record["strategy_key"] for record in payload["records"]] == [
        "asian_away_cover_hgb_bucket_v2",
        "asian_away_cover_hgb_edge_v1",
    ]
    assert payload["summary"]["total_records"] == 2
    simulation = payload["confidence_simulation"]
    assert simulation["summary"]["group_count"] == 1
    assert simulation["groups"][0]["triggered_strategy_keys"] == [
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    ]
    assert simulation["groups"][0]["signal_families"] == ["asian_away_hgb"]
    assert simulation["groups"][0]["suggested_stake_units"] == "1.25"
    assert simulation["groups"][0]["home_team_logo_url"] == "https://img.example/home.png"
    assert simulation["groups"][0]["away_team_logo_url"] == "https://img.example/away.png"
    assert simulation["groups"][0]["home_score"] is None
    assert simulation["groups"][0]["away_score"] is None
    assert len(simulation["groups"][0]["signal_record_ids"]) == 2
    assert scorer_calls == [str(match.id)]


def test_web_console_api_batch_records_skip_duplicate_paper_candidates(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United")
        away = Team(canonical_name="Waterford")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.90"),
                under_odds=Decimal("2.00"),
                match_winner_home_odds=Decimal("2.10"),
                match_winner_draw_odds=Decimal("3.25"),
                match_winner_away_odds=Decimal("3.40"),
            )
        )
        session.commit()

    scorer_calls = []

    def fake_scorer(row):
        from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore

        scorer_calls.append(row["match_id"])
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.7100"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.2100"),
            model_name="fake_hgb",
        )

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    first_response = client.post(
        "/api/paper-recommendations/records/batch",
        json={
            "candidates": [{"match_id": match.id, "strategy_key": "asian_away_cover_hgb_edge_v1"}],
            "hours": 6,
        },
    )
    assert first_response.status_code == 200
    scorer_calls.clear()

    response = client.post(
        "/api/paper-recommendations/records/batch",
        json={
            "candidates": [
                {"match_id": match.id, "strategy_key": "asian_away_cover_hgb_edge_v1"},
                {"match_id": match.id, "strategy_key": "asian_away_cover_hgb_bucket_v2"},
            ],
            "hours": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch_result"] == {
        "requested_count": 2,
        "created_count": 1,
        "skipped_count": 1,
        "skipped": [
            {
                "match_id": match.id,
                "strategy_key": "asian_away_cover_hgb_edge_v1",
                "reason": "duplicate active paper recommendation record",
            }
        ],
    }
    assert [record["strategy_key"] for record in payload["records"]] == [
        "asian_away_cover_hgb_bucket_v2",
        "asian_away_cover_hgb_edge_v1",
    ]
    assert scorer_calls == [str(match.id)]


def test_web_console_api_paper_workspace_cache_varies_by_latest_training_run(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls = []

    def fake_scorer(row):
        calls.append(row["match_id"])
        return None

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            paper_queue_scorer=fake_scorer,
            clock=lambda: datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United")
        away = Team(canonical_name="Waterford")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_name="api_football",
            source_match_id="17446",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add(
            OddsSnapshot(
                match=match,
                captured_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                data_source="api_football",
                bookmaker="Pinnacle",
                asian_handicap=Decimal("-0.50"),
                home_odds=Decimal("1.990"),
                away_odds=Decimal("1.930"),
                total_line=Decimal("2.50"),
                over_odds=Decimal("1.90"),
                under_odds=Decimal("2.00"),
                match_winner_home_odds=Decimal("2.10"),
                match_winner_draw_odds=Decimal("3.25"),
                match_winner_away_odds=Decimal("3.40"),
            )
        )
        session.commit()

    first_response = client.get("/api/paper-recommendations/workspace?hours=6")
    second_response = client.get("/api/paper-recommendations/workspace?hours=6")
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(calls) == 1

    with session_factory() as session:
        session.add(
            TrainingRun(
                run_type="full_refresh",
                status="success",
                started_at=datetime(2026, 5, 30, 1, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                finished_at=datetime(2026, 5, 30, 1, 40, tzinfo=ZoneInfo("Asia/Shanghai")),
                snapshot_tag="20260530-0130",
                current_step="finalize",
                dynamic_feature_path="local_data/training/new.csv",
            )
        )
        session.commit()

    third_response = client.get("/api/paper-recommendations/workspace?hours=6")

    assert third_response.status_code == 200
    assert len(calls) == 2


def test_web_console_api_backfills_paper_record_from_historical_candidate(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        home = Team(canonical_name="Drogheda United")
        away = Team(canonical_name="Waterford")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
            source_match_id="1492706",
        )
        session.add_all([league, home, away, match])
        session.commit()
        match_id = match.id

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            display_name_service=DisplayNameService(
                DisplayNames(
                    leagues={"Premier Division": "爱超"},
                    teams={"Drogheda United": "德罗赫达联", "Waterford": "沃特福德联"},
                )
            ),
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.post(
        "/api/paper-recommendations/records/backfill",
        json={
            "match_id": match_id,
            "market_line": "-0.50",
            "odds": "1.930",
            "model_probability": "0.6044",
            "market_probability": "0.4880",
            "edge": "0.1164",
            "manual_note": "从 20260530 paper queue 报告补录",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["match_id"] == match_id
    assert payload["league_display_name"] == "爱超"
    assert payload["home_team_display_name"] == "德罗赫达联"
    assert payload["away_team_display_name"] == "沃特福德联"
    assert payload["strategy_display_name"] == "亚盘客队方向 · HGB边际 v1"
    assert payload["recommended_handicap"] == "客队 +0.50"
    assert payload["current_market_line"] == "-0.50"
    assert payload["current_odds"] == "1.930"
    assert payload["model_probability"] == "0.6044"
    assert payload["market_probability"] == "0.4880"
    assert payload["edge"] == "0.1164"
    assert payload["is_manually_adjusted"] is True
    assert payload["manual_note"] == "从 20260530 paper queue 报告补录"
    assert "manual_backfill" in payload["risk_tags"]


def test_web_console_api_returns_match_list_workspace_and_detail(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Sanfrecce Hiroshima", logo_url="home.png")
        away = Team(canonical_name="Kawasaki Frontale", logo_url="away.png")
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add_all([league, home, away, match])
        session.flush()
        session.add_all(
            [
                HistoricalOddsSnapshot(
                    match_id=match.id,
                    source_name="oddspapi",
                    source_fixture_id="j1-1",
                    bookmaker="pinnacle",
                    market_type="asian_handicap",
                    market_id="ah",
                    market_name="Asian Handicap",
                    market_line=Decimal("-0.50"),
                    outcome_side="home",
                    odds=Decimal("1.900"),
                    snapshot_time=datetime(2026, 5, 30, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                    period="pre_match",
                ),
                HistoricalOddsSnapshot(
                    match_id=match.id,
                    source_name="oddspapi",
                    source_fixture_id="j1-1",
                    bookmaker="pinnacle",
                    market_type="asian_handicap",
                    market_id="ah",
                    market_name="Asian Handicap",
                    market_line=Decimal("-0.50"),
                    outcome_side="away",
                    odds=Decimal("1.950"),
                    snapshot_time=datetime(2026, 5, 30, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                    period="pre_match",
                ),
            ]
        )
        session.commit()
        match_id = match.id

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.get("/api/match-list/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["start_time"] == "2026-05-30T00:00:00+08:00"
    assert payload["filters"]["end_time"] == "2026-05-31T12:00:00+08:00"
    assert payload["total_matches"] == 1
    assert payload["matches"][0]["match_id"] == match_id
    assert payload["matches"][0]["odds_summary"]["asian_handicap"] == "客队 +0.50 @ 1.950"

    detail_response = client.get(f"/api/matches/{match_id}/detail")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["home_team_logo_url"] == "home.png"
    assert detail["has_odds"] is True
    assert detail["team_data_note"] == "待接入"
    assert detail["paper_recommendation_summary"]["label"] == "暂无纸面推荐记录"


def test_web_console_api_match_list_sync_buttons_record_runs(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls = []

    def fake_fixtures_results(match_ids: list[int]):
        calls.append(("fixtures_results", tuple(match_ids)))
        return {
            "success": [],
            "failed": [],
            "skipped": [],
            "requests": 3,
        }

    def fake_odds(match_ids: list[int]):
        calls.append(("odds", tuple(match_ids)))
        return {
            "success": [],
            "failed": [],
            "skipped": [],
            "requests": 5,
        }

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_fixtures_results_syncer=fake_fixtures_results,
            match_list_odds_syncer=fake_odds,
        )
    )

    fixtures_response = client.post("/api/match-list/sync/fixtures-results", json={"days": 3})
    odds_response = client.post("/api/match-list/sync/odds", json={"days": 2})

    assert fixtures_response.status_code == 200
    assert odds_response.status_code == 200
    assert calls == [("fixtures_results", ()), ("odds", ())]
    assert fixtures_response.json()["sync_run"]["sync_type"] == "fixtures_results"
    assert odds_response.json()["sync_run"]["requests_used"] == 5


def test_web_console_api_match_list_sync_uses_filtered_match_targets(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls = []
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        other_league = League(name="K League 1", country_or_region="Korea", level=1)
        session.add_all([league, other_league])
        session.flush()
        selected_ids = []
        for index in range(2):
            home = Team(canonical_name=f"Sanfrecce API {index}")
            away = Team(canonical_name=f"Kawasaki API {index}")
            session.add_all([home, away])
            session.flush()
            match = Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 30, 13, index, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
            )
            session.add(match)
            session.flush()
            selected_ids.append(match.id)
        other_home = Team(canonical_name="Ulsan API")
        other_away = Team(canonical_name="Daegu API")
        session.add_all([other_home, other_away])
        session.flush()
        session.add(
            Match(
                league=other_league,
                home_team=other_home,
                away_team=other_away,
                kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                status="scheduled",
            )
        )
        session.commit()

    def fake_fixtures_results(match_ids):
        calls.append(tuple(match_ids))
        return {
            "success": [
                {"match_id": match_ids[0], "message": "updated"},
            ],
            "failed": [
                {"match_id": match_ids[1], "message": "remote error"},
            ],
            "skipped": [],
            "requests": 2,
        }

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_fixtures_results_syncer=fake_fixtures_results,
        )
    )

    response = client.post(
        "/api/match-list/sync/fixtures-results",
        json={
            "start_time": "2026-05-30T00:00",
            "end_time": "2026-05-31T00:00",
            "league_name": "J1 League",
            "status_filter": "not_started",
            "odds_filter": "all",
            "search": "api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls == [tuple(selected_ids)]
    assert payload["report"]["target_count"] == 2
    assert payload["report"]["success_count"] == 1
    assert payload["report"]["failed_count"] == 1
    assert payload["report"]["success"][0]["match_id"] == selected_ids[0]
    assert payload["report"]["failed"][0]["message"] == "remote error"


def test_web_console_api_discovers_fixture_range_and_refreshes_match_list(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls = []

    def fake_fixture_range_syncer(start_time, end_time, league_name):
        calls.append((start_time, end_time, league_name))
        with session_factory() as session:
            league = League(
                name="J1 League",
                country_or_region="Japan",
                level=1,
                source_name="api_football",
                source_league_id="98",
            )
            home = Team(
                canonical_name="Sanfrecce Hiroshima",
                country_or_region="Japan",
                source_name="api_football",
                source_team_id="1",
            )
            away = Team(
                canonical_name="Kawasaki Frontale",
                country_or_region="Japan",
                source_name="api_football",
                source_team_id="2",
            )
            session.add_all([league, home, away])
            session.flush()
            session.add(
                Match(
                    league=league,
                    home_team=home,
                    away_team=away,
                    kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    status="scheduled",
                    source_name="api_football",
                    source_match_id="1494190",
                )
            )
            session.commit()
        return {"created": 1, "updated": 0, "skipped": 0, "requests": 1}

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_fixture_range_syncer=fake_fixture_range_syncer,
        )
    )

    response = client.post(
        "/api/match-list/sync/fixtures-range",
        json={
            "start_time": "2026-05-30T00:00:00+08:00",
            "end_time": "2026-05-30T23:59:00+08:00",
            "league_name": "J1 League",
        },
    )
    detail_response = client.get("/api/data-sync-runs/1/items")
    workspace_response = client.get(
        "/api/match-list/workspace?start_time=2026-05-30T00:00:00%2B08:00"
        "&end_time=2026-05-30T23:59:00%2B08:00"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sync_run"]["sync_type"] == "fixtures_range"
    assert payload["sync_run"]["created_count"] == 1
    assert payload["report"]["created_count"] == 1
    assert payload["report"]["updated_count"] == 0
    assert detail_response.status_code == 200
    assert detail_response.json()["report"]["created_count"] == 1
    assert calls == [
        (
            datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
            "J1 League",
        )
    ]
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()
    assert workspace["total_matches"] == 1
    assert workspace["matches"][0]["home_team_name"] == "Sanfrecce Hiroshima"


def test_web_console_api_fixtures_results_sync_does_not_show_odds_diagnostics(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Sanfrecce API")
        away = Team(canonical_name="Kawasaki API")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add(match)
        session.flush()
        match_id = match.id
        session.add(
            OddsSourceMatch(
                match_id=match_id,
                source_name="oddspapi",
                source_fixture_id="id1000064968995194",
                matched_at=datetime(2026, 5, 29, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=1.0,
                match_reason="exact",
                historical_odds_status="success",
                historical_odds_checked_at=datetime(2026, 5, 29, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                historical_odds_error=None,
            )
        )
        session.add(
            HistoricalOddsSnapshot(
                match_id=match_id,
                source_name="oddspapi",
                source_fixture_id="id1000064968995194",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="1064",
                market_name="Asian Handicap",
                market_line=Decimal("-0.50"),
                outcome_side="home",
                odds=Decimal("1.91"),
                snapshot_time=datetime(2026, 5, 29, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                period="fulltime",
                raw_payload=None,
            )
        )
        session.commit()

    def fake_fixtures_results(match_ids: list[int]):
        return {
            "success": [],
            "failed": [{"match_id": match_ids[0], "message": "connection reset"}],
            "skipped": [],
            "requests": 1,
        }

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_fixtures_results_syncer=fake_fixtures_results,
        )
    )

    response = client.post(
        "/api/match-list/sync/fixtures-results",
        json={
            "start_time": "2026-05-30T00:00",
            "end_time": "2026-05-31T00:00",
            "league_name": "J1 League",
            "status_filter": "all",
            "odds_filter": "all",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["sync_run"]["id"]
    failed = response.json()["report"]["failed"][0]
    assert failed["diagnostic_status"] is None
    assert failed["source_fixture_id"] is None
    assert failed["snapshot_count"] == 0

    detail_response = client.get(f"/api/data-sync-runs/{run_id}/items")

    assert detail_response.status_code == 200
    persisted_failed = detail_response.json()["report"]["failed"][0]
    assert persisted_failed["diagnostic_status"] is None
    assert persisted_failed["source_fixture_id"] is None
    assert persisted_failed["snapshot_count"] == 0


def test_match_list_fixtures_results_sync_skips_live_matches(monkeypatch, tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Live Home")
        away = Team(canonical_name="Live Away")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="live",
            status_short="1H",
            elapsed=35,
            home_score=1,
            away_score=0,
            source_name="api_football",
            source_match_id="1523174",
        )
        session.add(match)
        session.commit()
        match_id = match.id

    class FailingClient:
        request_count = 0

        def get(self, endpoint, params):
            raise AssertionError("live matches should not request API-Football fixtures")

    class Provider:
        client = FailingClient()

    monkeypatch.setattr(web_api, "_open_session_for_web_sync", lambda: session_factory())
    monkeypatch.setattr(web_api, "load_project_settings", lambda: object())
    monkeypatch.setattr(web_api, "build_api_football_provider", lambda settings: Provider())
    monkeypatch.setattr(
        web_api,
        "now_beijing",
        lambda: datetime(2026, 5, 30, 18, 35, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    result = web_api._run_match_list_fixtures_results_sync([match_id])

    assert result["success"] == []
    assert result["failed"] == []
    assert result["requests"] == 0
    assert result["skipped"] == [
        {
            "match_id": match_id,
            "message": "比赛进行中，暂不申请赛果",
        }
    ]


def test_match_list_fixtures_results_sync_refreshes_stale_live_matches(monkeypatch, tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(
            name="Super League",
            country_or_region="China",
            level=1,
            source_name="api_football",
            source_league_id="169",
        )
        home = Team(
            canonical_name="Sichuan Jiuniu",
            source_name="api_football",
            source_team_id="1",
        )
        away = Team(
            canonical_name="Qingdao Jonoon",
            source_name="api_football",
            source_team_id="2",
        )
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2026,
            status="2h",
            status_short="2H",
            status_long="Second Half",
            elapsed=90,
            home_score=3,
            away_score=2,
            source_name="api_football",
            source_match_id="1523176",
        )
        session.add(match)
        session.commit()
        match_id = match.id

    class FinishedClient:
        request_count = 0

        def get(self, endpoint, params):
            self.request_count += 1
            assert endpoint == "fixtures"
            assert params["id"] == "1523176"
            return {
                "response": [
                    {
                        "fixture": {
                            "id": 1523176,
                            "date": "2026-05-30T20:00:00+08:00",
                            "timezone": "Asia/Shanghai",
                            "timestamp": 1780142400,
                            "periods": {"first": 1780142400, "second": 1780146000},
                            "venue": {},
                            "status": {
                                "long": "Match Finished",
                                "short": "FT",
                                "elapsed": 90,
                                "extra": 11,
                            },
                        },
                        "league": {
                            "id": 169,
                            "name": "Super League",
                            "country": "China",
                            "season": 2026,
                        },
                        "teams": {
                            "home": {"id": 1, "name": "Sichuan Jiuniu", "winner": True},
                            "away": {"id": 2, "name": "Qingdao Jonoon", "winner": False},
                        },
                        "goals": {"home": 3, "away": 2},
                        "score": {
                            "halftime": {"home": 1, "away": 0},
                            "fulltime": {"home": 3, "away": 2},
                            "extratime": {"home": None, "away": None},
                            "penalty": {"home": None, "away": None},
                        },
                    }
                ]
            }

    class Provider:
        client = FinishedClient()

    monkeypatch.setattr(web_api, "_open_session_for_web_sync", lambda: session_factory())
    monkeypatch.setattr(web_api, "load_project_settings", lambda: object())
    monkeypatch.setattr(web_api, "build_api_football_provider", lambda settings: Provider())
    monkeypatch.setattr(
        web_api,
        "now_beijing",
        lambda: datetime(2026, 5, 30, 22, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    result = web_api._run_match_list_fixtures_results_sync([match_id])

    assert result["skipped"] == []
    assert result["failed"] == []
    assert result["requests"] == 1
    assert result["success"] == [
        {
            "match_id": match_id,
            "message": "赛程/赛果已刷新",
            "created": 0,
            "updated": 1,
            "requests": 1,
        }
    ]
    with session_factory() as session:
        refreshed = session.get(Match, match_id)
        assert refreshed.status == "finished"
        assert refreshed.status_short == "FT"
        assert refreshed.status_long == "Match Finished"


def test_web_console_api_single_match_sync_uses_only_path_match(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls = []
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Sanfrecce One")
        away = Team(canonical_name="Kawasaki One")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            status="scheduled",
        )
        session.add(match)
        session.commit()
        match_id = match.id

    def fake_odds(match_ids):
        calls.append(tuple(match_ids))
        return {
            "success": [{"match_id": match_ids[0], "message": "snapshots=12"}],
            "failed": [],
            "skipped": [],
            "requests": 3,
        }

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_odds_syncer=fake_odds,
        )
    )

    response = client.post(f"/api/matches/{match_id}/sync/odds", json={})

    assert response.status_code == 200
    assert calls == [(match_id,)]
    payload = response.json()
    assert payload["report"]["sync_type"] == "odds"
    assert payload["report"]["success"][0]["fixture"] == "Sanfrecce One vs Kawasaki One"


def test_web_console_api_persists_and_returns_match_sync_run_items(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    seeded = _seed_console_data(session_factory)
    failed_match_id: int | None = None

    def fake_odds(match_ids: list[int]):
        nonlocal failed_match_id
        with session_factory() as session:
            failed_match = session.query(Match).filter(Match.source_match_id == "1002").one()
            failed_match_id = failed_match.id
            source_match = session.query(OddsSourceMatch).filter_by(match_id=failed_match.id).one()
            source_match.source_fixture_id = "missing-fixture"
            source_match.historical_odds_status = "unavailable"
            source_match.historical_odds_checked_at = datetime(2026, 5, 30, 10, 2, tzinfo=ZoneInfo("Asia/Shanghai"))
            source_match.historical_odds_error = "OddsPapi HTTP error: status=404"
            session.commit()
        return {
            "success": [{"match_id": seeded["matched_match_id"], "message": "赔率已刷新"}],
            "failed": [{"match_id": failed_match_id, "message": "未获取到可用赔率"}],
            "skipped": [],
            "requests": 2,
        }

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            match_list_odds_syncer=fake_odds,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.post(
        "/api/match-list/sync/odds",
        json={
            "start_time": "2026-05-20T00:00",
            "end_time": "2026-05-22T23:59",
            "status_filter": "all",
            "odds_filter": "all",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["sync_run"]["id"]
    with session_factory() as session:
        items = (
            session.query(DataSyncRunItem)
            .filter(DataSyncRunItem.run_id == run_id)
            .order_by(DataSyncRunItem.status.desc(), DataSyncRunItem.match_id.asc())
            .all()
        )
        assert [(item.match_id, item.status) for item in items] == [
            (seeded["matched_match_id"], "success"),
            (failed_match_id, "failed"),
        ]
        failed = [item for item in items if item.status == "failed"][0]
        assert failed.diagnostic_status == "unavailable"
        assert failed.diagnostic_error == "OddsPapi HTTP error: status=404"
        assert failed.source_fixture_id == "missing-fixture"

    detail_response = client.get(f"/api/data-sync-runs/{run_id}/items")

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["sync_run"]["id"] == run_id
    assert payload["report"]["failed"][0]["diagnostic_status"] == "unavailable"
    assert payload["report"]["failed"][0]["diagnostic_error"] == "OddsPapi HTTP error: status=404"
    assert payload["report"]["failed"][0]["source_fixture_id"] == "missing-fixture"


def test_match_list_odds_sync_falls_back_to_live_odds_for_upcoming_match(monkeypatch):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(
            name="Allsvenskan",
            country_or_region="Sweden",
            level=1,
            source_name="api_football",
            source_league_id="113",
        )
        home = Team(canonical_name="Mjallby AIF")
        away = Team(canonical_name="Djurgardens IF")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 31, 22, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2026,
            status="scheduled",
            source_name="api_football",
            source_match_id="1494190",
        )
        session.add(match)
        session.commit()
        match_id = match.id

    class LiveOddsProvider:
        def __init__(self):
            self.client = type("Client", (), {"request_count": 0})()

        def fetch_odds_for_fixtures(self, fixture_ids):
            self.client.request_count += 1
            assert fixture_ids == ["1494190"]
            return [
                ExternalOddsSnapshot(
                    source_name="api_football",
                    source_match_id="1494190",
                    captured_at=datetime(2026, 5, 31, 20, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
                    bookmaker="Bet365",
                    asian_handicap=Decimal("-0.25"),
                    home_odds=Decimal("1.950"),
                    away_odds=Decimal("1.850"),
                    total_line=Decimal("2.75"),
                    over_odds=Decimal("1.910"),
                    under_odds=Decimal("1.990"),
                    match_winner_home_odds=Decimal("2.300"),
                    match_winner_draw_odds=Decimal("3.200"),
                    match_winner_away_odds=Decimal("2.900"),
                )
            ]

    def fake_historical_sync(**kwargs):
        with session_factory() as session:
            source_match = OddsSourceMatch(
                match_id=match_id,
                source_name="oddspapi",
                source_fixture_id="id1000004067126590",
                matched_at=datetime(2026, 5, 31, 20, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="league/time/team match; time_delta_seconds=0",
                historical_odds_status="unavailable",
                historical_odds_checked_at=datetime(2026, 5, 31, 20, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
                historical_odds_error="OddsPapi HTTP error: status=404",
            )
            session.add(source_match)
            session.commit()
        return type("Result", (), {"requests_used": 1})()

    monkeypatch.setattr(web_api, "_open_session_for_web_sync", lambda: session_factory())
    monkeypatch.setattr(web_api, "run_oddspapi_sync_result", fake_historical_sync)
    monkeypatch.setattr(web_api, "load_project_settings", lambda: object())
    monkeypatch.setattr(web_api, "build_api_football_provider", lambda settings: LiveOddsProvider())
    monkeypatch.setattr(
        web_api,
        "now_beijing",
        lambda: datetime(2026, 5, 31, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    result = web_api._run_match_list_odds_sync([match_id])

    assert result["failed"] == []
    assert result["success"] == [
        {
            "match_id": match_id,
            "message": "赔率已刷新",
        }
    ]
    assert result["requests"] == 2
    with session_factory() as session:
        assert session.query(HistoricalOddsSnapshot).filter_by(match_id=match_id).count() == 0
        live_snapshot = session.query(OddsSnapshot).filter_by(match_id=match_id).one()
        assert live_snapshot.data_source == "api_football"
        assert live_snapshot.asian_handicap == Decimal("-0.25")
        diagnostics = web_api._build_match_sync_diagnostics(session, [match_id])
        assert diagnostics[match_id]["diagnostic_status"] == "live_odds_fallback"
        assert diagnostics[match_id]["diagnostic_error"] is None
        assert diagnostics[match_id]["snapshot_count"] == 1


def test_match_list_odds_sync_does_not_fetch_live_odds_when_historical_exists(monkeypatch):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(
            name="Allsvenskan",
            country_or_region="Sweden",
            level=1,
            source_name="api_football",
            source_league_id="113",
        )
        home = Team(canonical_name="BK Hacken")
        away = Team(canonical_name="Hammarby FF")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 31, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2026,
            status="scheduled",
            source_name="api_football",
            source_match_id="1494188",
        )
        session.add(match)
        session.flush()
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id="id1000004067126588",
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="ah-1",
                market_name="Asian Handicap",
                market_line=Decimal("-0.50"),
                outcome_side="home",
                odds=Decimal("1.930"),
                snapshot_time=datetime(2026, 5, 31, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                period="prematch",
            )
        )
        session.commit()
        match_id = match.id

    class FailingProvider:
        client = type("Client", (), {"request_count": 0})()

        def fetch_odds_for_fixtures(self, fixture_ids):
            raise AssertionError("live odds fallback should not run when historical odds exist")

    def fake_historical_sync(**kwargs):
        return type("Result", (), {"requests_used": 1})()

    monkeypatch.setattr(web_api, "_open_session_for_web_sync", lambda: session_factory())
    monkeypatch.setattr(web_api, "run_oddspapi_sync_result", fake_historical_sync)
    monkeypatch.setattr(web_api, "load_project_settings", lambda: object())
    monkeypatch.setattr(web_api, "build_api_football_provider", lambda settings: FailingProvider())

    result = web_api._run_match_list_odds_sync([match_id])

    assert result["success"] == [{"match_id": match_id, "message": "赔率已刷新"}]
    assert result["failed"] == []
    assert result["requests"] == 1
    with session_factory() as session:
        assert session.query(OddsSnapshot).filter_by(match_id=match_id).count() == 0


def test_match_list_odds_sync_does_not_fetch_live_odds_after_kickoff(monkeypatch):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(
            name="Allsvenskan",
            country_or_region="Sweden",
            level=1,
            source_name="api_football",
            source_league_id="113",
        )
        home = Team(canonical_name="AIK")
        away = Team(canonical_name="IFK Goteborg")
        session.add_all([league, home, away])
        session.flush()
        match = Match(
            league=league,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 31, 19, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2026,
            status="scheduled",
            source_name="api_football",
            source_match_id="1494191",
        )
        session.add(match)
        session.commit()
        match_id = match.id

    class FailingProvider:
        client = type("Client", (), {"request_count": 0})()

        def fetch_odds_for_fixtures(self, fixture_ids):
            raise AssertionError("live odds fallback should not run after kickoff")

    def fake_historical_sync(**kwargs):
        return type("Result", (), {"requests_used": 1})()

    monkeypatch.setattr(web_api, "_open_session_for_web_sync", lambda: session_factory())
    monkeypatch.setattr(web_api, "run_oddspapi_sync_result", fake_historical_sync)
    monkeypatch.setattr(web_api, "load_project_settings", lambda: object())
    monkeypatch.setattr(web_api, "build_api_football_provider", lambda settings: FailingProvider())
    monkeypatch.setattr(
        web_api,
        "now_beijing",
        lambda: datetime(2026, 5, 31, 19, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    result = web_api._run_match_list_odds_sync([match_id])

    assert result["success"] == []
    assert result["failed"] == [{"match_id": match_id, "message": "未获取到可用赔率"}]
    assert result["requests"] == 1
    with session_factory() as session:
        assert session.query(OddsSnapshot).filter_by(match_id=match_id).count() == 0


def test_web_console_api_match_list_sync_invalidates_cached_workspace(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        league = League(name="J1 League", country_or_region="Japan", level=1)
        home = Team(canonical_name="Sanfrecce Hiroshima")
        away = Team(canonical_name="Kawasaki Frontale")
        session.add_all([league, home, away])
        session.commit()

    def fake_fixtures_results(days: int):
        with session_factory() as session:
            league = session.query(League).one()
            home = session.query(Team).filter(Team.canonical_name == "Sanfrecce Hiroshima").one()
            away = session.query(Team).filter(Team.canonical_name == "Kawasaki Frontale").one()
            session.add(
                Match(
                    league=league,
                    home_team=home,
                    away_team=away,
                    kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    status="scheduled",
                )
            )
            session.commit()
        return {"created": 1, "updated": 0, "skipped": 0, "requests": 1}

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            clock=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_list_fixtures_results_syncer=fake_fixtures_results,
        )
    )

    first_response = client.get("/api/match-list/workspace")
    sync_response = client.post("/api/match-list/sync/fixtures-results", json={"days": 3})
    second_response = client.get("/api/match-list/workspace")

    assert first_response.status_code == 200
    assert first_response.json()["total_matches"] == 0
    assert sync_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["total_matches"] == 1
    assert second_response.json()["matches"][0]["home_team_name"] == "Sanfrecce Hiroshima"


def test_web_console_api_returns_training_workspace(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    dataset_path = tmp_path / "baseline.csv"
    dataset_path.write_text(
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
    dataset_report_path = tmp_path / "dataset.md"
    qa_report_path = tmp_path / "qa.md"
    market_report_path = tmp_path / "market.md"
    dataset_report_path.write_text("dataset report", encoding="utf-8")
    qa_report_path.write_text("qa report", encoding="utf-8")
    market_report_path.write_text("market report", encoding="utf-8")

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            baseline_dataset_path=dataset_path,
            baseline_dataset_report_path=dataset_report_path,
            baseline_qa_report_path=qa_report_path,
            baseline_market_report_path=market_report_path,
        )
    )

    response = client.get("/api/training/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["exists"] is True
    assert payload["dataset"]["row_count"] == 1
    assert payload["dataset"]["column_count"] == 36
    assert payload["dataset_report"]["exists"] is True
    assert payload["qa"]["exists"] is True
    assert payload["qa"]["empty_required_cells"] == 0
    assert payload["qa"]["invalid_odds_cells"] == 0
    assert payload["market_baseline"]["exists"] is True
    assert payload["market_baseline"]["evaluated_market_samples"] == 3
    assert payload["market_baseline"]["market_reports"]["match_winner"]["flat_bet_roi"] == "1.1000"
    assert payload["latest_run"] is None


def test_web_console_api_returns_complete_training_workspace_when_dataset_is_missing(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            baseline_dataset_path=tmp_path / "missing-baseline.csv",
            baseline_dataset_report_path=tmp_path / "dataset.md",
            baseline_qa_report_path=tmp_path / "qa.md",
            baseline_market_report_path=tmp_path / "market.md",
        )
    )

    response = client.get("/api/training/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["exists"] is False
    assert payload["dataset"]["row_count"] == 0
    assert payload["qa"] == {
        "exists": False,
        "path": str(tmp_path / "qa.md"),
        "updated_at": None,
        "empty_required_cells": 0,
        "invalid_odds_cells": 0,
        "invalid_probability_cells": 0,
        "invalid_overround_cells": 0,
        "thin_history_count": 0,
        "thin_history_ratio": "0.0000",
        "low_sample_leagues": {},
    }
    assert payload["market_baseline"] == {
        "exists": False,
        "path": str(tmp_path / "market.md"),
        "updated_at": None,
        "market_samples": 0,
        "evaluated_market_samples": 0,
        "skipped_market_samples": 0,
        "market_reports": {},
    }


def test_web_console_api_starts_training_full_refresh(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    started: list[int] = []

    def fake_background_runner(run_id: int):
        started.append(run_id)

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            training_full_refresh_runner=fake_background_runner,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.post("/api/training/runs/full-refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["snapshot_tag"] == "20260530-1323"
    assert payload["current_step"] == "queued"
    assert started == [payload["id"]]


def test_web_console_api_rejects_second_training_full_refresh(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            training_full_refresh_runner=lambda run_id: None,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    first_response = client.post("/api/training/runs/full-refresh")
    second_response = client.post("/api/training/runs/full-refresh")

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["active_run_id"] == first_response.json()["id"]


def test_web_console_api_returns_latest_training_run(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            TrainingRun(
                run_type="full_refresh",
                status="success",
                started_at=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                finished_at=datetime(2026, 5, 30, 13, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
                snapshot_tag="20260530-1300",
                current_step="finalize",
                dataset_rows=5330,
                coverage_ratio=Decimal("0.8912"),
                last_trained_match_summary="日职联 神户胜利船 1-0 鹿岛鹿角",
                dataset_path="local_data/training/baseline.csv",
                total_goals_edge_stability_report_path="docs/模型实验/total-goals.md",
                total_goals_bucket_sandbox_report_path="docs/模型实验/total-goals-bucket.md",
            )
        )
        session.commit()

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))
    response = client.get("/api/training/runs/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_tag"] == "20260530-1300"
    assert payload["status"] == "success"
    assert payload["dataset_rows"] == 5330
    assert payload["coverage_ratio"] == "0.8912"
    assert payload["last_trained_match_summary"] == "日职联 神户胜利船 1-0 鹿岛鹿角"
    assert payload["artifact_paths"]["dataset_path"] == "local_data/training/baseline.csv"
    assert (
        payload["artifact_paths"]["total_goals_edge_stability_report_path"]
        == "docs/模型实验/total-goals.md"
    )
    assert (
        payload["artifact_paths"]["total_goals_bucket_sandbox_report_path"]
        == "docs/模型实验/total-goals-bucket.md"
    )
    assert payload["artifact_paths"]["total_goals_v3_signal_research_report_path"].endswith(
        "20260530-1300-baseline-total-goals-v3-signal-research.md"
    )
    assert payload["artifact_paths"]["model_consensus_signal_research_report_path"].endswith(
        "20260530-1300-baseline-model-consensus-signal-research.md"
    )


def _seed_console_data(session_factory):
    with session_factory() as session:
        league = League(
            name="英冠",
            country_or_region="England",
            level=2,
            priority=90,
            source_name="api-football",
            source_league_id="40",
        )
        cardiff = Team(canonical_name="Cardiff")
        swansea = Team(canonical_name="Swansea")
        wolves = Team(
            canonical_name="Wolves",
            logo_url="https://media.api-sports.io/football/teams/wolves.png",
        )
        leeds = Team(canonical_name="Leeds")
        session.add_all([league, cardiff, swansea, wolves, leeds])
        session.flush()

        matched_match = Match(
            league_id=league.id,
            home_team_id=cardiff.id,
            away_team_id=swansea.id,
            kickoff_time=datetime(2026, 5, 20, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2025,
            status="finished",
            home_score=2,
            away_score=1,
            source_name="api-football",
            source_match_id="1001",
        )
        unmatched_match = Match(
            league_id=league.id,
            home_team_id=wolves.id,
            away_team_id=leeds.id,
            kickoff_time=datetime(2026, 5, 21, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            season=2025,
            status="finished",
            home_score=0,
            away_score=0,
            source_name="api-football",
            source_match_id="1002",
        )
        session.add_all([matched_match, unmatched_match])
        session.flush()

        session.add(
            OddsSourceMatch(
                match_id=unmatched_match.id,
                source_name="oddspapi",
                source_fixture_id="",
                matched_at=datetime(2026, 5, 22, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("0.0000"),
                match_reason="未匹配到 OddsPapi 比赛",
                historical_odds_status="unmatched",
            )
        )
        session.add_all(
            [
                HistoricalOddsSnapshot(
                    match_id=matched_match.id,
                    source_name="oddspapi",
                    source_fixture_id="p1",
                    bookmaker="pinnacle",
                    market_type="asian_handicap",
                    market_id="ah-1",
                    market_name="Asian Handicap",
                    market_line=Decimal("-0.25"),
                    outcome_side="home",
                    odds=Decimal("1.930"),
                    snapshot_time=datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("UTC")),
                    period="prematch",
                ),
                HistoricalOddsSnapshot(
                    match_id=matched_match.id,
                    source_name="oddspapi",
                    source_fixture_id="p1",
                    bookmaker="pinnacle",
                    market_type="total_goals",
                    market_id="ou-1",
                    market_name="Total Goals",
                    market_line=Decimal("2.50"),
                    outcome_side="over",
                    odds=Decimal("1.910"),
                    snapshot_time=datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("UTC")),
                    period="prematch",
                ),
                HistoricalOddsSnapshot(
                    match_id=matched_match.id,
                    source_name="oddspapi",
                    source_fixture_id="p1",
                    bookmaker="pinnacle",
                    market_type="match_winner",
                    market_id="1x2",
                    market_name="Match Winner",
                    market_line=Decimal("0.00"),
                    outcome_side="home",
                    odds=Decimal("2.100"),
                    snapshot_time=datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("UTC")),
                    period="prematch",
                ),
                HistoricalOddsSnapshot(
                    match_id=matched_match.id,
                    source_name="oddspapi",
                    source_fixture_id="p1",
                    bookmaker="pinnacle",
                    market_type="match_winner",
                    market_id="1x2",
                    market_name="Match Winner",
                    market_line=Decimal("0.00"),
                    outcome_side="draw",
                    odds=Decimal("3.250"),
                    snapshot_time=datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("UTC")),
                    period="prematch",
                ),
                HistoricalOddsSnapshot(
                    match_id=matched_match.id,
                    source_name="oddspapi",
                    source_fixture_id="p1",
                    bookmaker="pinnacle",
                    market_type="match_winner",
                    market_id="1x2",
                    market_name="Match Winner",
                    market_line=Decimal("0.00"),
                    outcome_side="away",
                    odds=Decimal("3.400"),
                    snapshot_time=datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("UTC")),
                    period="prematch",
                ),
            ]
        )
        session.add(
            RecommendationRecord(
                match_id=matched_match.id,
                created_at=datetime(2026, 5, 20, 21, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
                league_name="英冠",
                home_team_name="Cardiff",
                away_team_name="Swansea",
                kickoff_time=datetime(2026, 5, 20, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                market_type="asian_handicap",
                side="home",
                market_line=Decimal("-0.25"),
                odds=Decimal("1.930"),
                model_probability=Decimal("0.5650"),
                market_implied_probability=Decimal("0.5181"),
                edge=Decimal("0.0469"),
                confidence_grade="A-",
                stake_units=Decimal("1.50"),
                status="pending",
            )
        )
        session.commit()
        return {"matched_match_id": matched_match.id}


def _add_complete_historical_odds(session, match: Match) -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=6)
    markets = [
        ("asian_handicap", Decimal("-0.50"), ("home", "away"), {"home": Decimal("1.990"), "away": Decimal("1.930")}),
        ("total_goals", Decimal("2.50"), ("over", "under"), {"over": Decimal("1.900"), "under": Decimal("2.000")}),
        (
            "match_winner",
            Decimal("0.00"),
            ("home", "draw", "away"),
            {"home": Decimal("2.100"), "draw": Decimal("3.250"), "away": Decimal("3.400")},
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
                period="prematch",
            )
        )

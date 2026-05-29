from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.display_service import DisplayNameService, DisplayNames, load_display_names
from icewine_prediction.display_translation_status_service import DisplayTranslationStatusService
from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    RecommendationRecord,
    Team,
)
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
    assert payload[0]["away_team_name"] == "Swansea"
    assert payload[0]["away_team_display_name"] == "斯旺西"
    assert payload[0]["market_type"] == "asian_handicap"
    assert payload[0]["confidence_grade"] == "A-"


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

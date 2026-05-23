from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.oddspapi_sync_runner import (
    OddsPapiSyncClient,
    build_oddspapi_sync_plan_for_session,
    format_oddspapi_sync_plan,
    run_oddspapi_sync_for_session,
    select_oddspapi_candidate_matches,
)
from icewine_prediction.sources.oddspapi_client import OddsPapiApiError


class FakeOddsPapiClient:
    def __init__(self, fail_endpoint=None):
        self.request_count = 0
        self.calls = []
        self.fail_endpoint = fail_endpoint
        self.failed_historical_fixture_ids = set()

    def get(self, endpoint, params=None):
        self.request_count += 1
        self.calls.append((endpoint, params or {}))
        if endpoint == self.fail_endpoint:
            raise OddsPapiApiError("rate limited")
        if (
            endpoint == "historical-odds"
            and params
            and params.get("fixtureId") in self.failed_historical_fixture_ids
        ):
            raise OddsPapiApiError("historical odds unavailable")
        if endpoint == "fixtures":
            return [
                {
                    "fixtureId": "oddspapi-fixture-1",
                    "tournamentId": 8,
                    "startTime": "2026-05-23T19:00:00Z",
                    "participant1Name": "RCD Mallorca",
                    "participant2Name": "Real Oviedo",
                }
            ]
        if endpoint == "historical-odds":
            return {
                "fixtureId": "oddspapi-fixture-1",
                "bookmakers": {
                    "pinnacle": {
                        "markets": {
                            "1070": {
                                "outcomes": {
                                    "1070": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": "2026-05-23T18:00:00Z",
                                                    "price": 1.91,
                                                }
                                            ]
                                        }
                                    },
                                    "1071": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": "2026-05-23T18:00:00Z",
                                                    "price": 1.99,
                                                }
                                            ]
                                        }
                                    },
                                }
                            },
                            "10170": {
                                "outcomes": {
                                    "10170": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": "2026-05-23T18:05:00Z",
                                                    "price": 1.88,
                                                }
                                            ]
                                        }
                                    },
                                    "10171": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": "2026-05-23T18:05:00Z",
                                                    "price": 2.02,
                                                }
                                            ]
                                        }
                                    },
                                }
                            },
                        }
                    }
                },
            }
        if endpoint == "markets":
            return [
                {
                    "marketId": 1070,
                    "marketName": "Asian Handicap",
                    "marketType": "spreads",
                    "period": "fulltime",
                    "handicap": -0.25,
                    "outcomes": [
                        {"outcomeId": 1070, "outcomeName": "1"},
                        {"outcomeId": 1071, "outcomeName": "2"},
                    ],
                },
                {
                    "marketId": 10170,
                    "marketName": "Over Under Full Time",
                    "marketType": "totals",
                    "period": "fulltime",
                    "handicap": 2.25,
                    "outcomes": [
                        {"outcomeId": 10170, "outcomeName": "Over"},
                        {"outcomeId": 10171, "outcomeName": "Under"},
                    ],
                },
            ]
        raise AssertionError(f"unexpected endpoint: {endpoint}")


def _match(
    session,
    source_match_id: str = "1391195",
    league_name: str = "La Liga",
    source_league_id: str = "140",
    kickoff_time: datetime | None = None,
    home_team_name: str = "Mallorca",
    away_team_name: str = "Oviedo",
):
    league = League(
        name=league_name,
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id=source_league_id,
    )
    home_team = Team(canonical_name=home_team_name)
    away_team = Team(canonical_name=away_team_name)
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=kickoff_time
        or datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        home_score=2,
        away_score=1,
        source_name="api_football",
        source_match_id=source_match_id,
    )
    session.add(match)
    session.commit()
    return match


def test_select_oddspapi_candidate_matches_prioritizes_league_then_recentness(session):
    premier_league = _match(
        session,
        source_match_id="pl",
        league_name="Premier League",
        source_league_id="39",
        kickoff_time=datetime(2026, 5, 20, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Chelsea",
        away_team_name="Tottenham",
    )
    la_liga = _match(
        session,
        source_match_id="laliga",
        league_name="La Liga",
        source_league_id="140",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Barcelona",
        away_team_name="Real Betis",
    )
    bundesliga = _match(
        session,
        source_match_id="bundesliga",
        league_name="Bundesliga",
        source_league_id="78",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Bayern Munich",
        away_team_name="Dortmund",
    )

    matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=3,
    )

    assert skipped == 0
    assert matches == [premier_league, la_liga, bundesliga]


def test_build_oddspapi_sync_plan_for_session_does_not_request_api(session):
    _match(session)
    client = FakeOddsPapiClient()

    result = build_oddspapi_sync_plan_for_session(
        session=session,
        season=2025,
        max_matches=20,
    )

    assert result.candidate_match_count == 1
    assert result.estimated_request_count == 3
    assert client.calls == []


def test_format_oddspapi_sync_plan_includes_candidate_matches(session):
    match = _match(session)

    plan = build_oddspapi_sync_plan_for_session(
        session=session,
        season=2025,
        max_matches=20,
    )

    output = format_oddspapi_sync_plan(plan)

    assert "候选比赛 1" in output
    assert "La Liga" in output
    assert "Mallorca vs Oviedo" in output
    assert str(match.id) in output


def test_run_oddspapi_sync_for_session_matches_fixture_and_stores_odds(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 1
    assert result.matched_count == 1
    assert result.inserted_snapshot_count == 4
    assert result.asian_handicap_count == 2
    assert result.total_goals_count == 2
    assert client.request_count == 3
    assert session.query(HistoricalOddsSnapshot).count() == 4


def test_run_oddspapi_sync_for_session_samples_snapshots_before_storing(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
        max_snapshots_per_match=2,
    )

    assert result.inserted_snapshot_count == 2
    assert session.query(HistoricalOddsSnapshot).count() == 2


def test_run_oddspapi_sync_for_session_skips_matches_with_existing_historical_odds(session):
    match = _match(session)
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="oddspapi-fixture-1",
            bookmaker="pinnacle",
            market_type="asian_handicap",
            market_id="1070",
            market_name="Asian Handicap",
            market_line=Decimal("-0.25"),
            outcome_side="home",
            odds=Decimal("1.91"),
            snapshot_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")),
            period="fulltime",
        )
    )
    session.commit()
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 0
    assert result.skipped_existing_odds_count == 1
    assert raw_client.calls == []


def test_run_oddspapi_sync_for_session_reuses_existing_source_match(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="oddspapi-fixture-1",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 1
    assert result.matched_count == 1
    assert result.inserted_snapshot_count == 4
    assert [call[0] for call in raw_client.calls] == ["historical-odds", "markets"]


def test_run_oddspapi_sync_for_session_stops_gracefully_on_api_error(session):
    _match(session)
    raw_client = FakeOddsPapiClient(fail_endpoint="fixtures")
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 0
    assert result.requests_used == 1
    assert result.failed_match_count == 1
    assert result.error_message == "1 场比赛失败，已跳过继续"


def test_run_oddspapi_sync_for_session_continues_after_single_match_odds_error(session):
    failed_match = _match(
        session,
        source_match_id="failed",
        league_name="Premier League",
        source_league_id="39",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Mallorca",
        away_team_name="Oviedo",
    )
    success_match = _match(
        session,
        source_match_id="success",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Mallorca B",
        away_team_name="Oviedo B",
    )
    session.add_all(
        [
            OddsSourceMatch(
                match_id=failed_match.id,
                source_name="oddspapi",
                source_fixture_id="failed-fixture",
                matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="cached",
            ),
            OddsSourceMatch(
                match_id=success_match.id,
                source_name="oddspapi",
                source_fixture_id="oddspapi-fixture-1",
                matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="cached",
            ),
        ]
    )
    session.commit()
    raw_client = FakeOddsPapiClient()
    raw_client.failed_historical_fixture_ids.add("failed-fixture")
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 1
    assert result.failed_match_count == 1
    assert result.matched_count == 2
    assert result.inserted_snapshot_count == 4
    assert result.error_message == "1 场比赛失败，已跳过继续"
    assert session.query(HistoricalOddsSnapshot).count() == 4


def test_run_oddspapi_sync_for_session_reports_progress(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)
    messages = []

    run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
        progress_callback=messages.append,
    )

    assert messages[0].startswith("[1/1] 开始")
    assert "Mallorca vs Oviedo" in messages[0]
    assert any("拉取历史赔率" in message for message in messages)
    assert any("拉取盘口定义" in message for message in messages)
    assert any("写入历史赔率" in message for message in messages)
    assert messages[-1].startswith("[1/1] 完成")


def test_run_oddspapi_sync_for_session_skips_requested_match_ids(session):
    skipped_match = _match(
        session,
        source_match_id="skipped",
        league_name="Premier League",
        source_league_id="39",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Skipped Home",
        away_team_name="Skipped Away",
    )
    kept_match = _match(
        session,
        source_match_id="kept",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Mallorca",
        away_team_name="Oviedo",
    )
    session.add(
        OddsSourceMatch(
            match_id=kept_match.id,
            source_name="oddspapi",
            source_fixture_id="oddspapi-fixture-1",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)
    messages = []

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
        skip_match_ids={skipped_match.id},
        progress_callback=messages.append,
    )

    assert result.processed_match_count == 1
    assert result.inserted_snapshot_count == 4
    assert all("Skipped Home" not in message for message in messages)
    assert [call[0] for call in raw_client.calls] == ["historical-odds", "markets"]


def test_oddspapi_sync_client_requests_fixture_and_historical_odds_payloads():
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    fixtures = client.fetch_fixtures(
        tournament_id=8,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    historical_odds = client.fetch_historical_odds(source_fixture_id="oddspapi-fixture-1")

    assert fixtures[0].fixture_id == "oddspapi-fixture-1"
    market_definitions = client.fetch_markets(source_fixture_id="oddspapi-fixture-1")

    assert "pinnacle" in historical_odds["bookmakers"]
    assert market_definitions[0]["marketId"] == 1070
    assert raw_client.calls[0][0] == "fixtures"
    assert raw_client.calls[0][1]["sportId"] == 10
    assert raw_client.calls[0][1]["tournamentId"] == 8
    assert raw_client.calls[0][1]["statusId"] == 2
    assert raw_client.calls[0][1]["hasOdds"] is True
    assert raw_client.calls[0][1]["from"] == "2026-05-23T17:00:00Z"
    assert raw_client.calls[0][1]["to"] == "2026-05-23T21:00:00Z"
    assert raw_client.calls[1] == (
        "historical-odds",
        {
            "sportId": 10,
            "fixtureId": "oddspapi-fixture-1",
            "bookmakers": "pinnacle,bet365,sbobet",
        },
    )
    assert raw_client.calls[2] == (
        "markets",
        {
            "sportId": 10,
            "fixtureId": "oddspapi-fixture-1",
            "bookmakers": "pinnacle,bet365,sbobet",
        },
    )

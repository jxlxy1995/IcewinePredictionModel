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
    run_oddspapi_sync_for_session,
)
from icewine_prediction.sources.oddspapi_client import OddsPapiApiError


class FakeOddsPapiClient:
    def __init__(self, fail_endpoint=None):
        self.request_count = 0
        self.calls = []
        self.fail_endpoint = fail_endpoint

    def get(self, endpoint, params=None):
        self.request_count += 1
        self.calls.append((endpoint, params or {}))
        if endpoint == self.fail_endpoint:
            raise OddsPapiApiError("rate limited")
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


def _match(session, source_match_id: str = "1391195"):
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
    )
    home_team = Team(canonical_name="Mallorca")
    away_team = Team(canonical_name="Oviedo")
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
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


def test_build_oddspapi_sync_plan_for_session_does_not_request_api(session):
    _match(session)
    client = FakeOddsPapiClient()

    result = build_oddspapi_sync_plan_for_session(
        session=session,
        season=2025,
        max_matches=20,
    )

    assert result.candidate_match_count == 1
    assert result.estimated_request_count == 2
    assert client.calls == []


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
    assert result.error_message == "rate limited"


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

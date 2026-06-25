from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    HistoricalOddsRawSnapshot,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME
from icewine_prediction.the_odds_api_sync_runner import (
    API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS,
    TheOddsApiSyncClient,
    build_the_odds_api_sync_plan_for_session,
    find_best_the_odds_api_event_match,
    run_the_odds_api_sync_for_session,
)


class FakeTheOddsApiClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.request_count = 0

    def get(self, endpoint, params=None):
        self.calls.append((endpoint, params or {}))
        self.request_count += 1
        return self.payloads[endpoint]


def test_sport_key_mapping_contains_mainstream_leagues():
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["140"] == "soccer_spain_la_liga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["78"] == "soccer_germany_bundesliga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["179"] == "soccer_spl"


def test_find_best_the_odds_api_event_match_uses_time_and_team_names(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    events = [
        {
            "id": "bad-time",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "commence_time": "2026-06-26T12:00:00Z",
        },
        {
            "id": "event-1",
            "home_team": "Arsenal FC",
            "away_team": "Chelsea",
            "commence_time": "2026-06-26T19:00:00Z",
        },
    ]

    candidate = find_best_the_odds_api_event_match(match, events)

    assert candidate is not None
    assert candidate.event_id == "event-1"
    assert candidate.confidence == Decimal("1.0000")


def test_run_the_odds_api_sync_stores_snapshots_under_distinct_source(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "sports/soccer_epl/odds": [
                    _featured_event_payload("2026-06-26T18:45:00Z")
                ],
                "sports/soccer_epl/events/event-1/odds": _empty_alternate_event_payload("event-1"),
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
    )

    assert result.processed_match_count == 1
    assert result.matched_count == 1
    assert result.inserted_snapshot_count == 7
    snapshots = session.query(HistoricalOddsSnapshot).all()
    assert {snapshot.source_name for snapshot in snapshots} == {THE_ODDS_API_SOURCE_NAME}
    assert {snapshot.bookmaker for snapshot in snapshots} == {"pinnacle"}
    status = session.query(OddsSourceMatch).one()
    assert status.source_name == THE_ODDS_API_SOURCE_NAME
    assert status.source_fixture_id == "event-1"
    assert status.historical_odds_status == "success"


def test_run_the_odds_api_sync_stores_raw_neighbor_summary_for_alternate_markets(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "sports/soccer_epl/odds": [
                    _featured_event_payload("2026-06-26T18:45:00Z"),
                ],
                "sports/soccer_epl/events/event-1/odds": _alternate_event_payload(
                    "2026-06-26T18:45:00Z"
                ),
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 25, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    main_lines = {
        row.market_line
        for row in session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match.id)
        .filter(HistoricalOddsSnapshot.market_type == "total_goals")
        .all()
    }
    raw_lines = {
        row.market_line
        for row in session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsRawSnapshot.market_type == "total_goals")
        .all()
    }

    assert result.inserted_snapshot_count == 7
    assert main_lines == {Decimal("2.5")}
    assert raw_lines == {Decimal("2.25"), Decimal("2.5"), Decimal("2.75")}
    assert (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.source_name == "oddspapi")
        .count()
        == 0
    )


def test_the_odds_api_sync_client_fetches_historical_odds_with_date():
    raw_client = FakeTheOddsApiClient(
        {
            "historical/sports/soccer_epl/odds": {
                "timestamp": "2026-06-26T18:50:00Z",
                "previous_timestamp": "2026-06-26T18:45:00Z",
                "next_timestamp": "2026-06-26T18:55:00Z",
                "data": [],
            }
        }
    )
    client = TheOddsApiSyncClient(raw_client)

    events = client.fetch_historical_odds(
        "soccer_epl",
        datetime(2026, 6, 26, 18, 50, tzinfo=ZoneInfo("UTC")),
    )

    assert events == []
    assert raw_client.calls == [
        (
            "historical/sports/soccer_epl/odds",
            {
                "regions": "eu",
                "bookmakers": "pinnacle",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "date": "2026-06-26T18:50:00Z",
            },
        )
    ]


def test_run_the_odds_api_sync_uses_standard_historical_timepoints_for_passed_kickoff_match(session):
    match = _add_match(
        session,
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        status="finished",
    )
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "historical/sports/soccer_epl/odds": {
                    "data": [
                        _historical_event_payload("2026-06-26T18:50:00Z"),
                    ],
                },
                "historical/sports/soccer_epl/events/historical-event-1/odds": {
                    "data": _empty_alternate_event_payload("historical-event-1"),
                }
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        from_date=datetime(2026, 6, 1, tzinfo=ZoneInfo("UTC")),
        now=datetime(2026, 6, 27, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert result.processed_match_count == 1
    assert result.inserted_snapshot_count == 18
    assert [call[0] for call in client.client.calls if call[0] == "historical/sports/soccer_epl/odds"] == [
        "historical/sports/soccer_epl/odds",
        "historical/sports/soccer_epl/odds",
        "historical/sports/soccer_epl/odds",
        "historical/sports/soccer_epl/odds",
        "historical/sports/soccer_epl/odds",
        "historical/sports/soccer_epl/odds",
    ]
    assert [call[1]["date"] for call in client.client.calls if call[0] == "historical/sports/soccer_epl/odds"] == [
        "2026-06-26T18:00:00Z",
        "2026-06-26T18:30:00Z",
        "2026-06-26T18:35:00Z",
        "2026-06-26T18:40:00Z",
        "2026-06-26T18:45:00Z",
        "2026-06-26T18:50:00Z",
    ]
    snapshots = session.query(HistoricalOddsSnapshot).all()
    assert {snapshot.source_name for snapshot in snapshots} == {THE_ODDS_API_SOURCE_NAME}
    assert {snapshot.source_fixture_id for snapshot in snapshots} == {"historical-event-1"}
    assert {
        snapshot.snapshot_time.replace(tzinfo=ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
        for snapshot in snapshots
    } == {
        "2026-06-26T18:00:00Z",
        "2026-06-26T18:30:00Z",
        "2026-06-26T18:35:00Z",
        "2026-06-26T18:40:00Z",
        "2026-06-26T18:45:00Z",
        "2026-06-26T18:50:00Z",
    }


def test_build_the_odds_api_sync_plan_skips_matches_with_existing_source_snapshots(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name=THE_ODDS_API_SOURCE_NAME,
            source_fixture_id="event-1",
            bookmaker="pinnacle",
            market_type="asian_handicap",
            market_id="event-1:spreads:-0.25:home",
            market_name="Asian Handicap",
            market_line=Decimal("-0.25"),
            outcome_side="home",
            odds=Decimal("1.91"),
            snapshot_time=datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
            period="full_time",
        )
    )
    session.commit()

    plan = build_the_odds_api_sync_plan_for_session(session=session, season=2026, max_matches=5)

    assert plan.candidate_match_count == 0
    assert plan.skipped_existing_odds_count == 1


def _add_match(
    session,
    *,
    home_team_name: str,
    away_team_name: str,
    source_league_id: str = "39",
    kickoff_time: datetime | None = None,
    status: str = "scheduled",
) -> Match:
    league = League(
        name="Premier League",
        country_or_region="England",
        level=1,
        is_enabled=True,
        source_name="api_football",
        source_league_id=source_league_id,
    )
    home = Team(canonical_name=home_team_name)
    away = Team(canonical_name=away_team_name)
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time or datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status=status,
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.commit()
    return match


def _historical_event_payload(last_update: str) -> dict:
    return {
        "id": "historical-event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": last_update,
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": "Chelsea", "price": 3.40},
                        ],
                    },
                ],
            }
        ],
    }


def _featured_event_payload(last_update: str) -> dict:
    return {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": last_update,
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": last_update,
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": "Chelsea", "price": 3.40},
                        ],
                    },
                    {
                        "key": "spreads",
                        "last_update": last_update,
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.91, "point": -0.25},
                            {"name": "Chelsea", "price": 1.99, "point": 0.25},
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": last_update,
                        "outcomes": [
                            {"name": "Over", "price": 1.92, "point": 2.5},
                            {"name": "Under", "price": 1.98, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }


def _alternate_event_payload(last_update: str) -> dict:
    return {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": last_update,
                "markets": [
                    {
                        "key": "alternate_totals",
                        "last_update": last_update,
                        "outcomes": [
                            {"name": "Over", "price": 1.65, "point": 2.25},
                            {"name": "Under", "price": 2.30, "point": 2.25},
                            {"name": "Over", "price": 1.92, "point": 2.5},
                            {"name": "Under", "price": 1.98, "point": 2.5},
                            {"name": "Over", "price": 2.30, "point": 2.75},
                            {"name": "Under", "price": 1.65, "point": 2.75},
                        ],
                    },
                ],
            }
        ],
    }


def _empty_alternate_event_payload(event_id: str) -> dict:
    return {
        "id": event_id,
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [],
    }

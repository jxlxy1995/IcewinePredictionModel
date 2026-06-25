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
                    {
                        "id": "event-1",
                        "home_team": "Arsenal",
                        "away_team": "Chelsea",
                        "commence_time": "2026-06-26T19:00:00Z",
                        "bookmakers": [
                            {
                                "key": "pinnacle",
                                "last_update": "2026-06-26T18:45:00Z",
                                "markets": [
                                    {
                                        "key": "h2h",
                                        "outcomes": [
                                            {"name": "Arsenal", "price": 2.10},
                                            {"name": "Draw", "price": 3.30},
                                            {"name": "Chelsea", "price": 3.40},
                                        ],
                                    },
                                    {
                                        "key": "spreads",
                                        "outcomes": [
                                            {"name": "Arsenal", "price": 1.91, "point": -0.25},
                                            {"name": "Chelsea", "price": 1.99, "point": 0.25},
                                        ],
                                    },
                                    {
                                        "key": "totals",
                                        "outcomes": [
                                            {"name": "Over", "price": 1.88, "point": 2.5},
                                            {"name": "Under", "price": 2.02, "point": 2.5},
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
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
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.commit()
    return match

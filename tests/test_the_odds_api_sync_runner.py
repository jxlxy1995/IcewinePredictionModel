from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from icewine_prediction.models import (
    ExternalAlias,
    HistoricalOddsRawSnapshot,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.odds_source_match_service import ExternalAliasInput
from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME
from icewine_prediction.the_odds_api_sync_runner import (
    API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS,
    TheOddsApiSyncClient,
    build_the_odds_api_sync_plan_for_session,
    find_best_the_odds_api_event_match,
    run_the_odds_api_sync_for_session,
    _load_team_aliases,
)


class FakeTheOddsApiClient:
    def __init__(self, payloads, *, credit_count=0):
        self.payloads = payloads
        self.calls = []
        self.request_count = 0
        self.credit_count = credit_count
        self.last_credit_count = 0
        self.provider_requests_used = None
        self.provider_requests_remaining = None

    def get(self, endpoint, params=None):
        self.calls.append((endpoint, params or {}))
        self.request_count += 1
        return self.payloads[endpoint]


def test_sport_key_mapping_contains_mainstream_leagues():
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["140"] == "soccer_spain_la_liga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["78"] == "soccer_germany_bundesliga"
    assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS["179"] == "soccer_spl"


def test_sport_key_mapping_covers_the_odds_api_supported_whitelist_leagues():
    expected_mappings = {
        "2": "soccer_uefa_champs_league",
        "3": "soccer_uefa_europa_league",
        "848": "soccer_uefa_europa_conference_league",
        "357": "soccer_league_of_ireland",
        "141": "soccer_spain_segunda_division",
        "144": "soccer_belgium_first_div",
        "203": "soccer_turkey_super_league",
        "197": "soccer_greece_super_league",
        "218": "soccer_austria_bundesliga",
        "207": "soccer_switzerland_superleague",
        "235": "soccer_russia_premier_league",
        "106": "soccer_poland_ekstraklasa",
        "119": "soccer_denmark_superliga",
        "128": "soccer_argentina_primera_division",
        "265": "soccer_chile_campeonato",
        "244": "soccer_finland_veikkausliiga",
        "113": "soccer_sweden_allsvenskan",
        "114": "soccer_sweden_superettan",
        "41": "soccer_england_league1",
        "103": "soccer_norway_eliteserien",
        "307": "soccer_saudi_arabia_pro_league",
        "169": "soccer_china_superleague",
    }

    for league_id, sport_key in expected_mappings.items():
        assert API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS[league_id] == sport_key
    assert len(API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS) >= 41


def test_the_odds_api_unsupported_leagues_config_matches_enabled_whitelist():
    config_dir = Path("config")
    leagues = yaml.safe_load((config_dir / "leagues.yaml").read_text(encoding="utf-8"))["leagues"]
    unsupported = yaml.safe_load(
        (config_dir / "the_odds_api_unsupported_leagues.yaml").read_text(encoding="utf-8")
    )["unsupported_leagues"]

    enabled_ids = {str(item["api_football_id"]) for item in leagues if item["enabled"]}
    expected_unsupported_ids = enabled_ids - set(API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS)
    configured_unsupported_ids = {str(item["api_football_id"]) for item in unsupported}

    assert configured_unsupported_ids == expected_unsupported_ids
    assert "357" not in configured_unsupported_ids


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


def test_find_best_the_odds_api_event_match_uses_external_team_aliases(session):
    match = _add_match(session, home_team_name="Türkiye", away_team_name="USA")
    events = [
        {
            "id": "world-cup-turkey-usa",
            "home_team": "Turkey",
            "away_team": "USA",
            "commence_time": "2026-06-26T19:00:00Z",
        },
    ]

    candidate = find_best_the_odds_api_event_match(
        match,
        events,
        team_aliases=[
            ExternalAliasInput(
                canonical_name="Türkiye",
                alias_name="Turkey",
            )
        ],
    )

    assert candidate is not None
    assert candidate.event_id == "world-cup-turkey-usa"
    assert candidate.confidence == Decimal("1.0000")


def test_load_the_odds_api_team_aliases_includes_config_and_database_aliases(
    session,
    tmp_path,
    monkeypatch,
):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(
            [
                "aliases:",
                "  - entity_type: team",
                "    source_name: the_odds_api",
                "    canonical_name: Türkiye",
                "    alias_name: Turkey",
                "  - entity_type: team",
                "    source_name: oddspapi",
                "    canonical_name: Wolves",
                "    alias_name: Wolverhampton Wanderers",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name=THE_ODDS_API_SOURCE_NAME,
            canonical_name="USA",
            alias_name="United States",
            normalized_alias="united states",
            created_at=datetime(2026, 6, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    session.commit()

    aliases = _load_team_aliases(session)

    assert ExternalAliasInput(canonical_name="Türkiye", alias_name="Turkey") in aliases
    assert ExternalAliasInput(canonical_name="USA", alias_name="United States") in aliases
    assert ExternalAliasInput(canonical_name="Wolves", alias_name="Wolverhampton Wanderers") in aliases


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
        now=datetime(2026, 6, 25, 0, 0, tzinfo=ZoneInfo("UTC")),
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


def test_run_the_odds_api_sync_does_not_fetch_alternate_markets_by_default(session):
    match = _add_match(session, home_team_name="Arsenal", away_team_name="Chelsea")
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "sports/soccer_epl/odds": [
                    _featured_event_payload("2026-06-26T18:45:00Z"),
                ],
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
    called_endpoints = [call[0] for call in client.client.calls]
    raw_total_count = (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsRawSnapshot.market_type == "total_goals")
        .count()
    )

    assert result.inserted_snapshot_count == 7
    assert main_lines == {Decimal("2.5")}
    assert "sports/soccer_epl/events/event-1/odds" not in called_endpoints
    assert raw_total_count == 2
    assert (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.source_name == "oddspapi")
        .count()
        == 0
    )


def test_run_the_odds_api_sync_can_fetch_alternate_markets_when_enabled(session):
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
        ),
        fetch_alternate_markets=True,
    )

    run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 25, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    raw_lines = {
        row.market_line
        for row in session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsRawSnapshot.market_type == "total_goals")
        .all()
    }

    assert raw_lines == {Decimal("2.25"), Decimal("2.5"), Decimal("2.75")}


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
    assert result.requests_used == 6
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


def test_run_the_odds_api_sync_selects_main_markets_from_each_historical_timepoint(session):
    match = _add_match(
        session,
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        status="finished",
    )

    class DateAwareHistoricalClient(FakeTheOddsApiClient):
        def get(self, endpoint, params=None):
            params = params or {}
            self.calls.append((endpoint, params))
            self.request_count += 1
            request_date = params.get("date")
            if request_date == "2026-06-26T18:00:00Z":
                return {
                    "data": [
                        _historical_event_payload_with_markets(
                            "2026-06-26T17:55:00Z",
                            asian_line="-1.00",
                            asian_home_price="1.95",
                            asian_away_price="1.92",
                            total_line="3.00",
                            over_price="1.95",
                            under_price="1.92",
                            h2h_home_price="1.58",
                            h2h_draw_price="4.30",
                            h2h_away_price="5.40",
                        )
                    ]
                }
            return {
                "data": [
                    _historical_event_payload_with_markets(
                        "2026-06-26T18:25:00Z",
                        asian_line="-0.75",
                        asian_home_price="1.84",
                        asian_away_price="2.04",
                        total_line="2.75",
                        over_price="1.84",
                        under_price="2.04",
                        h2h_home_price="1.67",
                        h2h_draw_price="4.25",
                        h2h_away_price="4.70",
                    )
                ]
            }

    client = TheOddsApiSyncClient(DateAwareHistoricalClient({}))

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        from_date=datetime(2026, 6, 1, tzinfo=ZoneInfo("UTC")),
        now=datetime(2026, 6, 27, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert result.inserted_snapshot_count == 42
    t30 = datetime(2026, 6, 26, 18, 30, tzinfo=ZoneInfo("UTC"))
    saved_t30 = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match.id)
        .filter(HistoricalOddsSnapshot.snapshot_time == t30)
        .all()
    )
    raw_t30 = (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .filter(HistoricalOddsRawSnapshot.snapshot_time == t30)
        .all()
    )

    assert {
        (row.market_type, row.market_line, row.outcome_side, row.odds)
        for row in saved_t30
        if row.market_type in {"asian_handicap", "total_goals"}
    } == {
        ("asian_handicap", Decimal("-0.75"), "home", Decimal("1.840")),
        ("asian_handicap", Decimal("-0.75"), "away", Decimal("2.040")),
        ("total_goals", Decimal("2.75"), "over", Decimal("1.840")),
        ("total_goals", Decimal("2.75"), "under", Decimal("2.040")),
    }
    assert {
        (row.market_type, row.market_line)
        for row in raw_t30
        if row.market_type in {"asian_handicap", "total_goals"}
    } == {
        ("asian_handicap", Decimal("-0.75")),
        ("total_goals", Decimal("2.75")),
    }
    assert {
        (row.outcome_side, row.odds)
        for row in saved_t30
        if row.market_type == "match_winner"
    } == {
        ("home", Decimal("1.670")),
        ("draw", Decimal("4.250")),
        ("away", Decimal("4.700")),
    }


def test_run_the_odds_api_sync_reuses_historical_sport_requests_within_batch(session):
    first = _add_match(
        session,
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        status="finished",
    )
    home = Team(canonical_name="Tottenham")
    away = Team(canonical_name="Everton")
    session.add_all([home, away])
    session.flush()
    second = Match(
        league=first.league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        season=2026,
        status="finished",
        source_name="api_football",
        source_match_id="1002",
    )
    session.add(second)
    session.commit()
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "historical/sports/soccer_epl/odds": {
                    "data": [
                        _historical_event_payload(
                            "2026-06-26T18:50:00Z",
                            event_id="historical-event-1",
                            home_team="Arsenal",
                            away_team="Chelsea",
                        ),
                        _historical_event_payload(
                            "2026-06-26T18:50:00Z",
                            event_id="historical-event-2",
                            home_team="Tottenham",
                            away_team="Everton",
                        ),
                    ],
                },
            },
            credit_count=180,
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        match_ids={first.id, second.id},
        now=datetime(2026, 6, 27, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    historical_calls = [
        call for call in client.client.calls if call[0] == "historical/sports/soccer_epl/odds"
    ]

    assert result.processed_match_count == 2
    assert result.inserted_snapshot_count == 36
    assert result.requests_used == 6
    assert result.credits_used == 180
    assert len(historical_calls) == 6


def test_run_the_odds_api_sync_uses_elapsed_historical_timepoints_before_kickoff(session):
    match = _add_match(
        session,
        home_team_name="Arsenal",
        away_team_name="Chelsea",
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        status="scheduled",
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
                },
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 26, 18, 51, tzinfo=ZoneInfo("UTC")),
    )

    assert result.processed_match_count == 1
    assert result.inserted_snapshot_count == 18
    assert [call[1]["date"] for call in client.client.calls if call[0] == "historical/sports/soccer_epl/odds"] == [
        "2026-06-26T18:00:00Z",
        "2026-06-26T18:30:00Z",
        "2026-06-26T18:35:00Z",
        "2026-06-26T18:40:00Z",
        "2026-06-26T18:45:00Z",
        "2026-06-26T18:50:00Z",
    ]


def test_run_the_odds_api_sync_uses_configured_team_aliases_for_historical_match(
    session,
    tmp_path,
    monkeypatch,
):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(
            [
                "aliases:",
                "  - entity_type: team",
                "    source_name: the_odds_api",
                "    canonical_name: Türkiye",
                "    alias_name: Turkey",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    match = _add_match(
        session,
        home_team_name="Türkiye",
        away_team_name="USA",
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        status="finished",
    )
    client = TheOddsApiSyncClient(
        FakeTheOddsApiClient(
            {
                "historical/sports/soccer_epl/odds": {
                    "data": [
                        _historical_event_payload(
                            "2026-06-26T18:50:00Z",
                            event_id="world-cup-turkey-usa",
                            home_team="Turkey",
                            away_team="USA",
                        ),
                    ],
                },
                "historical/sports/soccer_epl/events/world-cup-turkey-usa/odds": {
                    "data": _empty_alternate_event_payload(
                        "world-cup-turkey-usa",
                        home_team="Turkey",
                        away_team="USA",
                    ),
                },
            }
        )
    )

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=client,
        season=2026,
        max_matches=5,
        now=datetime(2026, 6, 27, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert result.processed_match_count == 1
    assert result.matched_count == 1
    assert result.inserted_snapshot_count == 18
    assert {
        row.source_fixture_id
        for row in session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match.id)
        .all()
    } == {"world-cup-turkey-usa"}


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


def _historical_event_payload(
    last_update: str,
    *,
    event_id: str = "historical-event-1",
    home_team: str = "Arsenal",
    away_team: str = "Chelsea",
) -> dict:
    return {
        "id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": last_update,
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": home_team, "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": away_team, "price": 3.40},
                        ],
                    },
                ],
            }
        ],
    }


def _historical_event_payload_with_markets(
    last_update: str,
    *,
    asian_line: str,
    asian_home_price: str,
    asian_away_price: str,
    total_line: str,
    over_price: str,
    under_price: str,
    h2h_home_price: str,
    h2h_draw_price: str,
    h2h_away_price: str,
    event_id: str = "historical-event-1",
    home_team: str = "Arsenal",
    away_team: str = "Chelsea",
) -> dict:
    asian_home_point = float(Decimal(asian_line))
    asian_away_point = float(-Decimal(asian_line))
    total_point = float(Decimal(total_line))
    return {
        "id": event_id,
        "home_team": home_team,
        "away_team": away_team,
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
                            {"name": home_team, "price": float(Decimal(h2h_home_price))},
                            {"name": "Draw", "price": float(Decimal(h2h_draw_price))},
                            {"name": away_team, "price": float(Decimal(h2h_away_price))},
                        ],
                    },
                    {
                        "key": "spreads",
                        "last_update": last_update,
                        "outcomes": [
                            {
                                "name": home_team,
                                "price": float(Decimal(asian_home_price)),
                                "point": asian_home_point,
                            },
                            {
                                "name": away_team,
                                "price": float(Decimal(asian_away_price)),
                                "point": asian_away_point,
                            },
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": last_update,
                        "outcomes": [
                            {
                                "name": "Over",
                                "price": float(Decimal(over_price)),
                                "point": total_point,
                            },
                            {
                                "name": "Under",
                                "price": float(Decimal(under_price)),
                                "point": total_point,
                            },
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


def _empty_alternate_event_payload(
    event_id: str,
    *,
    home_team: str = "Arsenal",
    away_team: str = "Chelsea",
) -> dict:
    return {
        "id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [],
    }

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    ExternalAlias,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.oddspapi_sync_runner import (
    OddsPapiSyncClient,
    build_oddspapi_match_report,
    build_oddspapi_match_report_for_session,
    build_oddspapi_probe_report_for_session,
    build_oddspapi_sync_plan_for_session,
    format_oddspapi_probe_report,
    format_oddspapi_sync_plan,
    run_oddspapi_sync_for_session,
    select_oddspapi_candidate_matches,
    _select_history_outcome_ids,
)
import icewine_prediction.oddspapi_sync_runner as oddspapi_sync_runner
from icewine_prediction.sources.oddspapi_client import OddsPapiApiError
from icewine_prediction.sources.oddspapi_client import OddsPapiRequestBudgetExceededError


class FakeOddsPapiClient:
    def __init__(self, fail_endpoint=None):
        self.request_count = 0
        self.request_budget = 10_000
        self.calls = []
        self.fail_endpoint = fail_endpoint
        self.failed_historical_fixture_ids = set()
        self.failed_historical_outcome_ids = set()

    def get(self, endpoint, params=None):
        if self.request_count >= self.request_budget:
            raise OddsPapiRequestBudgetExceededError("OddsPapi request budget exceeded")
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
        if (
            endpoint == "historical-odds"
            and params
            and str(params.get("outcomeId")) in self.failed_historical_outcome_ids
        ):
            raise OddsPapiApiError("outcome historical odds unavailable")
        if endpoint == "fixtures":
            if (params or {}).get("tournamentId") == 17:
                return [
                    {
                        "fixtureId": "oddspapi-wolves-fulham",
                        "tournamentId": 17,
                        "startTime": "2026-05-17T14:00:00Z",
                        "participant1Name": "Wolverhampton Wanderers",
                        "participant2Name": "Fulham FC",
                    }
                ]
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
            fixture_id = (params or {}).get("fixtureId")
            created_at = (
                "2026-05-17T13:00:00Z"
                if fixture_id == "oddspapi-wolves-fulham"
                else "2026-05-23T18:00:00Z"
            )
            total_created_at = (
                "2026-05-17T13:05:00Z"
                if fixture_id == "oddspapi-wolves-fulham"
                else "2026-05-23T18:05:00Z"
            )
            payload = {
                "fixtureId": fixture_id or "oddspapi-fixture-1",
                "bookmakers": {
                    "pinnacle": {
                        "markets": {
                            "1070": {
                                "outcomes": {
                                    "1070": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": created_at,
                                                    "price": 1.91,
                                                }
                                            ]
                                        }
                                    },
                                    "1071": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": created_at,
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
                                                    "createdAt": total_created_at,
                                                    "price": 1.88,
                                                }
                                            ]
                                        }
                                    },
                                    "10171": {
                                        "players": {
                                            "0": [
                                                {
                                                    "createdAt": total_created_at,
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
            outcome_id = str((params or {}).get("outcomeId") or "")
            if outcome_id:
                for bookmaker_payload in payload["bookmakers"].values():
                    for market_id in list(bookmaker_payload["markets"]):
                        market_payload = bookmaker_payload["markets"][market_id]
                        filtered_outcomes = {
                            key: value
                            for key, value in market_payload["outcomes"].items()
                            if key == outcome_id
                        }
                        if filtered_outcomes:
                            market_payload["outcomes"] = filtered_outcomes
                        else:
                            del bookmaker_payload["markets"][market_id]
            return payload
        if endpoint == "markets":
            if (params or {}).get("fixtureId") in self.failed_historical_fixture_ids:
                raise OddsPapiApiError("markets unavailable")
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


def test_select_oddspapi_candidate_matches_skips_unavailable_or_empty_historical_odds(session):
    empty_match = _match(session, source_match_id="empty", league_name="La Liga Empty")
    unavailable_match = _match(
        session,
        source_match_id="unavailable",
        league_name="La Liga Unavailable",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Barcelona",
        away_team_name="Real Betis",
    )
    retryable_match = _match(
        session,
        source_match_id="retryable",
        league_name="La Liga Retryable",
        kickoff_time=datetime(2026, 5, 22, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Real Madrid",
        away_team_name="Sevilla",
    )
    fresh_match = _match(
        session,
        source_match_id="fresh",
        league_name="La Liga Fresh",
        kickoff_time=datetime(2026, 5, 21, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Valencia",
        away_team_name="Getafe",
    )
    session.add_all(
        [
            OddsSourceMatch(
                match_id=empty_match.id,
                source_name="oddspapi",
                source_fixture_id="empty-fixture",
                matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="cached",
                historical_odds_status="empty",
            ),
            OddsSourceMatch(
                match_id=unavailable_match.id,
                source_name="oddspapi",
                source_fixture_id="unavailable-fixture",
                matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="cached",
                historical_odds_status="unavailable",
            ),
            OddsSourceMatch(
                match_id=retryable_match.id,
                source_name="oddspapi",
                source_fixture_id="retryable-fixture",
                matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                match_confidence=Decimal("1.0000"),
                match_reason="cached",
                historical_odds_status="failed",
            ),
        ]
    )
    session.commit()

    matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
    )

    assert skipped == 2
    assert matches == [retryable_match, fresh_match]


def test_select_oddspapi_candidate_matches_filters_by_league_ids_and_from_date(session):
    old_laliga = _match(
        session,
        source_match_id="old-laliga",
        league_name="La Liga Old",
        source_league_id="140",
        kickoff_time=datetime(2025, 12, 31, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Barcelona",
        away_team_name="Valencia",
    )
    new_laliga = _match(
        session,
        source_match_id="new-laliga",
        league_name="La Liga New",
        source_league_id="140",
        kickoff_time=datetime(2026, 1, 20, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Real Madrid",
        away_team_name="Sevilla",
    )
    _match(
        session,
        source_match_id="serie-a",
        league_name="Serie A",
        source_league_id="135",
        kickoff_time=datetime(2026, 1, 21, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Inter",
        away_team_name="Roma",
    )

    matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
        league_ids={"140"},
        from_date=datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert skipped == 0
    assert old_laliga not in matches
    assert matches == [new_laliga]


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


def test_build_oddspapi_probe_report_checks_markets_only(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    report = build_oddspapi_probe_report_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert report.probed_match_count == 1
    assert report.available_match_count == 1
    assert report.failed_match_count == 0
    assert report.requests_used == 2
    assert report.matches[0].match_id == 1
    assert report.matches[0].available is True
    assert report.matches[0].outcome_count == 4
    assert [call[0] for call in raw_client.calls] == ["fixtures", "markets"]


def test_build_oddspapi_probe_report_marks_market_failures(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="failed-fixture",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()
    raw_client = FakeOddsPapiClient()
    raw_client.failed_historical_fixture_ids.add("failed-fixture")
    client = OddsPapiSyncClient(raw_client)

    report = build_oddspapi_probe_report_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert report.probed_match_count == 1
    assert report.available_match_count == 0
    assert report.failed_match_count == 1
    assert report.matches[0].available is False
    assert report.matches[0].reason == "markets unavailable"


def test_format_oddspapi_probe_report_includes_skip_ids(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)
    report = build_oddspapi_probe_report_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    output = format_oddspapi_probe_report(report)

    assert "探测比赛 1" in output
    assert "可回填 1" in output
    assert "推荐跳过 -" in output
    assert "outcomes=4" in output


def test_select_history_outcome_ids_returns_all_standard_handicap_and_total_outcomes():
    markets = [
        {
            "marketId": 106,
            "marketName": "Over Under Full Time",
            "marketType": "totals",
            "handicap": 0.5,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 106, "outcomeName": "Over"},
                {"outcomeId": 107, "outcomeName": "Under"},
            ],
        },
        {
            "marketId": 1010,
            "marketName": "Over Under Full Time",
            "marketType": "totals",
            "handicap": 2.5,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 1010, "outcomeName": "Over"},
                {"outcomeId": 1011, "outcomeName": "Under"},
            ],
        },
        {
            "marketId": 200,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": -2.5,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 200, "outcomeName": "1"},
                {"outcomeId": 201, "outcomeName": "2"},
            ],
        },
        {
            "marketId": 210,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": -0.25,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 210, "outcomeName": "1"},
                {"outcomeId": 211, "outcomeName": "2"},
            ],
        },
    ]

    outcome_ids = _select_history_outcome_ids(markets)

    assert outcome_ids == ["106", "107", "1010", "1011", "200", "201", "210", "211"]


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


def test_run_oddspapi_sync_for_session_uses_stored_team_aliases(session):
    _match(
        session,
        league_name="Premier League",
        source_league_id="39",
        kickoff_time=datetime(2026, 5, 17, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Wolves",
        away_team_name="Fulham",
    )
    session.add(
        ExternalAlias(
            entity_type="team",
            source_name="oddspapi",
            canonical_name="Wolves",
            alias_name="Wolverhampton Wanderers",
            normalized_alias="wolverhampton wanderers",
            created_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
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
    assert [call[0] for call in raw_client.calls] == [
        "markets",
        "historical-odds",
    ]
    assert raw_client.calls[1][1].get("outcomeId") is None


def test_run_oddspapi_sync_for_session_reuses_fixture_lookup_for_same_time_window(session):
    _match(
        session,
        source_match_id="first",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Mallorca",
        away_team_name="Oviedo",
    )
    _match(
        session,
        source_match_id="second",
        league_name="La Liga Same Window",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Barcelona",
        away_team_name="Valencia",
    )
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    fixture_calls = [call for call in raw_client.calls if call[0] == "fixtures"]
    assert len(fixture_calls) == 1


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
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
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


def test_run_oddspapi_sync_for_session_marks_404_odds_error_as_unavailable(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="missing-fixture",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()

    class MissingHistoricalOddsClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            self.request_count += 1
            self.calls.append((endpoint, params or {}))
            if endpoint == "historical-odds":
                raise OddsPapiApiError("OddsPapi HTTP error: status=404")
            return super().get(endpoint, params)

    raw_client = MissingHistoricalOddsClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    assert result.failed_match_count == 1
    assert source_match.historical_odds_status == "unavailable"
    assert source_match.historical_odds_error == "OddsPapi HTTP error: status=404"


def test_run_oddspapi_sync_for_session_marks_429_odds_error_as_retryable_failed(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="rate-limited-fixture",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()

    class RateLimitedHistoricalOddsClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            self.request_count += 1
            self.calls.append((endpoint, params or {}))
            if endpoint == "historical-odds":
                raise OddsPapiApiError("OddsPapi HTTP error: status=429")
            return super().get(endpoint, params)

    raw_client = RateLimitedHistoricalOddsClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    assert result.failed_match_count == 1
    assert source_match.historical_odds_status == "failed"
    assert source_match.historical_odds_error == "OddsPapi HTTP error: status=429"


def test_run_oddspapi_sync_for_session_continues_after_single_outcome_odds_error(session):
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
    raw_client.failed_historical_outcome_ids.add("1070")
    client = OddsPapiSyncClient(raw_client)
    messages = []

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
        progress_callback=messages.append,
    )

    assert result.processed_match_count == 1
    assert result.failed_match_count == 0
    assert result.inserted_snapshot_count == 4
    assert result.asian_handicap_count == 2
    assert result.total_goals_count == 2
    assert all("跳过历史赔率" not in message for message in messages)


def test_run_oddspapi_sync_for_session_stops_gracefully_on_request_budget(session):
    _match(session)
    raw_client = FakeOddsPapiClient()
    raw_client.request_budget = 2
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    assert result.processed_match_count == 0
    assert result.failed_match_count == 0
    assert result.requests_used == 2
    assert result.error_message == "OddsPapi request budget exceeded"


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
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
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
    assert [call[0] for call in raw_client.calls] == [
        "markets",
        "historical-odds",
    ]


def test_build_oddspapi_match_report_displays_snapshot_time_in_beijing(session):
    match = _match(session)
    session.add(
        HistoricalOddsSnapshot(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="oddspapi-fixture-1",
            bookmaker="pinnacle",
            market_type="total_goals",
            market_id="10170",
            market_name="Over Under Full Time",
            market_line=Decimal("2.50"),
            outcome_side="over",
            odds=Decimal("1.90"),
            snapshot_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")),
            period="fulltime",
        )
    )
    session.commit()

    output = build_oddspapi_match_report_for_session(session, match.id)

    assert "2026-05-24 02:00:00 北京时间" in output


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
            "bookmakers": "pinnacle",
        },
    )
    assert raw_client.calls[2] == (
        "markets",
        {
            "sportId": 10,
            "fixtureId": "oddspapi-fixture-1",
            "bookmakers": "pinnacle",
        },
    )


def test_oddspapi_sync_client_respects_historical_odds_cooldown(monkeypatch):
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client, historical_odds_cooldown_seconds=5)
    now_values = iter([100.0, 100.0, 101.0, 105.0])
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "monotonic", lambda: next(now_values))
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    client.fetch_historical_odds(source_fixture_id="oddspapi-fixture-1", outcome_id="1070")
    client.fetch_historical_odds(source_fixture_id="oddspapi-fixture-1", outcome_id="1071")

    assert sleeps == [4.0]


def test_oddspapi_sync_client_respects_fixture_cooldown_after_request_error(monkeypatch):
    raw_client = FakeOddsPapiClient(fail_endpoint="fixtures")
    client = OddsPapiSyncClient(raw_client)
    now_values = iter([100.0, 100.0, 101.0, 102.0])
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "monotonic", lambda: next(now_values))
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    try:
        client.fetch_fixtures(
            tournament_id=8,
            kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    except OddsPapiApiError:
        pass
    try:
        client.fetch_fixtures(
            tournament_id=8,
            kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    except OddsPapiApiError:
        pass

    assert sleeps == [1.0]

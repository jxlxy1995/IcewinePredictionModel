from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import (
    ExternalAlias,
    HistoricalOddsRawSnapshot,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    Team,
)
from icewine_prediction.oddspapi_sync_runner import (
    GLOBAL_MARKET_DEFINITIONS_CACHE,
    OddsPapiRequestLimiter,
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
from icewine_prediction.odds_source_match_service import ExternalAliasInput
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
    status: str = "finished",
    home_score: int | None = 2,
    away_score: int | None = 1,
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
        status=status,
        home_score=home_score,
        away_score=away_score,
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


def test_select_oddspapi_candidate_matches_includes_unfinished_matches_when_targeted(session):
    scheduled_match = _match(
        session,
        source_match_id="scheduled-j1",
        league_name="J1 League",
        source_league_id="98",
        kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Sanfrecce Hiroshima",
        away_team_name="Kawasaki Frontale",
        status="scheduled",
        home_score=None,
        away_score=None,
    )

    untargeted_matches, _ = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
    )
    targeted_matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
        match_ids={scheduled_match.id},
    )

    assert scheduled_match not in untargeted_matches
    assert skipped == 0
    assert targeted_matches == [scheduled_match]


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


def test_select_oddspapi_candidate_matches_retries_terminal_status_when_targeted(session):
    unavailable_match = _match(
        session,
        source_match_id="targeted-unavailable",
        league_name="J1 League",
        source_league_id="98",
    )
    session.add(
        OddsSourceMatch(
            match_id=unavailable_match.id,
            source_name="oddspapi",
            source_fixture_id="",
            matched_at=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("0.0000"),
            match_reason="unavailable",
            historical_odds_status="unavailable",
        )
    )
    session.commit()

    untargeted_matches, _ = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
    )
    targeted_matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
        match_ids={unavailable_match.id},
    )

    assert unavailable_match not in untargeted_matches
    assert skipped == 0
    assert targeted_matches == [unavailable_match]


def test_select_oddspapi_candidate_matches_skips_unmatched_historical_odds(session):
    unmatched_match = _match(
        session,
        source_match_id="unmatched",
        league_name="La Liga Unmatched",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Barcelona",
        away_team_name="Real Betis",
    )
    fresh_match = _match(
        session,
        source_match_id="fresh-after-unmatched",
        league_name="La Liga Fresh",
        kickoff_time=datetime(2026, 5, 22, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Valencia",
        away_team_name="Getafe",
    )
    session.add(
        OddsSourceMatch(
            match_id=unmatched_match.id,
            source_name="oddspapi",
            source_fixture_id="",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("0.0000"),
            match_reason="unmatched",
            historical_odds_status="unmatched",
        )
    )
    session.commit()

    matches, skipped = select_oddspapi_candidate_matches(
        session=session,
        season=2025,
        max_matches=10,
    )

    assert skipped == 1
    assert matches == [fresh_match]


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


def test_select_history_outcome_ids_returns_candidate_handicap_total_and_match_winner_outcomes():
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
        {
            "marketId": 9001,
            "marketName": "1X2 Full Time",
            "marketType": "moneyline",
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 9001, "outcomeName": "1"},
                {"outcomeId": 9002, "outcomeName": "X"},
                {"outcomeId": 9003, "outcomeName": "2"},
            ],
        },
    ]

    outcome_ids = _select_history_outcome_ids(markets)

    assert outcome_ids == [
        "210",
        "211",
        "200",
        "201",
        "1010",
        "1011",
        "106",
        "107",
        "9001",
        "9002",
        "9003",
    ]


def test_select_history_outcome_ids_keeps_distinct_candidate_lines_when_market_families_duplicate():
    markets = [
        {
            "marketId": 1072,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": 0,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 1072, "outcomeName": "1"},
                {"outcomeId": 1073, "outcomeName": "2"},
            ],
        },
        {
            "marketId": 1586,
            "marketName": "Handicap",
            "marketType": "spreads",
            "handicap": 0,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 1586, "outcomeName": "1"},
                {"outcomeId": 1587, "outcomeName": "2"},
            ],
        },
        {
            "marketId": 22306,
            "marketName": "Handicap",
            "marketType": "spreads",
            "handicap": 0,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 22306, "outcomeName": "1"},
                {"outcomeId": 22307, "outcomeName": "2"},
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
        {
            "marketId": 220,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": 0.25,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 220, "outcomeName": "1"},
                {"outcomeId": 221, "outcomeName": "2"},
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
            "marketId": 1514,
            "marketName": "Total",
            "marketType": "totals",
            "handicap": 2.5,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 1514, "outcomeName": "Over"},
                {"outcomeId": 1515, "outcomeName": "Under"},
            ],
        },
        {
            "marketId": 10170,
            "marketName": "Over Under Full Time",
            "marketType": "totals",
            "handicap": 2.25,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 10170, "outcomeName": "Over"},
                {"outcomeId": 10171, "outcomeName": "Under"},
            ],
        },
        {
            "marketId": 10270,
            "marketName": "Over Under Full Time",
            "marketType": "totals",
            "handicap": 2.75,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 10270, "outcomeName": "Over"},
                {"outcomeId": 10271, "outcomeName": "Under"},
            ],
        },
    ]

    outcome_ids = _select_history_outcome_ids(markets)

    assert outcome_ids == [
        "1072",
        "1073",
        "210",
        "211",
        "220",
        "221",
        "1010",
        "1011",
        "10170",
        "10171",
        "10270",
        "10271",
    ]


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


def test_load_team_aliases_includes_configured_aliases(session, tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "external_aliases.yaml").write_text(
        "\n".join(
            [
                "aliases:",
                "  - entity_type: team",
                "    source_name: oddspapi",
                "    canonical_name: Dynamo",
                "    alias_name: FK Dinamo Moscow",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    aliases = oddspapi_sync_runner._load_team_aliases(session)

    assert ExternalAliasInput(
        canonical_name="Dynamo",
        alias_name="FK Dinamo Moscow",
    ) in aliases


def test_api_football_turkish_super_lig_maps_to_oddspapi_turkiye_super_lig():
    assert oddspapi_sync_runner.API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS["203"] == 52


def test_api_football_league_mappings_include_new_sleep_backfill_targets():
    mappings = oddspapi_sync_runner.API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS

    assert mappings["61"] == 34
    assert mappings["71"] == 325
    assert mappings["144"] == 38
    assert mappings["169"] == 649
    assert mappings["179"] == 36
    assert mappings["188"] == 136
    assert mappings["207"] == 215
    assert mappings["218"] == 45
    assert mappings["265"] == 27665


def test_api_football_league_mappings_include_east_asia_and_mls_targets():
    mappings = oddspapi_sync_runner.API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS

    assert mappings["98"] == 196
    assert mappings["253"] == 242
    assert mappings["292"] == 410
    assert mappings["293"] == 777


def test_api_football_league_mappings_include_2025_sample_targets():
    mappings = oddspapi_sync_runner.API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS

    assert mappings["197"] == 185
    assert mappings["307"] == 955


def test_api_football_league_mappings_include_new_main_leagues():
    mappings = oddspapi_sync_runner.API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS

    assert mappings["357"] == 192
    assert mappings["1087"] == 55
    assert mappings["104"] == 22
    assert mappings["120"] == 47
    assert mappings["274"] == 1015


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
    assert "outcomeId" not in raw_client.calls[1][1]


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
    assert len(fixture_calls) == 2
    assert fixture_calls[0][1]["statusId"] == 2
    assert fixture_calls[0][1]["hasOdds"] is True
    assert "statusId" not in fixture_calls[1][1]
    assert "hasOdds" not in fixture_calls[1][1]


def test_run_oddspapi_sync_for_session_stops_gracefully_on_api_error(session):
    match = _match(session)
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
    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    assert source_match.source_fixture_id == ""
    assert source_match.historical_odds_status == "fixture_lookup_failed"
    assert source_match.historical_odds_error == "rate limited"


def test_run_oddspapi_sync_for_session_marks_404_fixture_error_as_unavailable(session):
    match = _match(session)

    class MissingFixtureClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            self.request_count += 1
            self.calls.append((endpoint, params or {}))
            if endpoint == "fixtures":
                raise OddsPapiApiError("OddsPapi HTTP error: status=404")
            return super().get(endpoint, params)

    raw_client = MissingFixtureClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    assert result.processed_match_count == 0
    assert result.failed_match_count == 1
    assert source_match.source_fixture_id == ""
    assert source_match.historical_odds_status == "unavailable"
    assert source_match.historical_odds_error == "OddsPapi HTTP error: status=404"


def test_run_oddspapi_sync_for_session_marks_unmatched_match_as_terminal(session):
    unmatched_match = _match(
        session,
        source_match_id="unmatched",
        source_league_id="140",
        kickoff_time=datetime(2026, 5, 23, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Unknown Home",
        away_team_name="Unknown Away",
    )
    raw_client = FakeOddsPapiClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=unmatched_match.id).one()
    assert result.processed_match_count == 0
    assert result.failed_match_count == 0
    assert source_match.source_fixture_id == ""
    assert source_match.match_confidence == Decimal("0.0000")
    assert source_match.match_reason == "未匹配到 OddsPapi 比赛"
    assert source_match.historical_odds_status == "unmatched"


def test_run_oddspapi_sync_for_session_retries_unfiltered_fixture_lookup_when_filtered_candidates_miss(session):
    match = _match(
        session,
        source_match_id="1497589",
        league_name="Superettan (Sweden)",
        source_league_id="114",
        kickoff_time=datetime(2026, 5, 30, 23, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        home_team_name="Osters IF",
        away_team_name="Norrby IF",
    )

    class FilteredFixtureMissClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            if endpoint == "fixtures" and (params or {}).get("tournamentId") == 46:
                self.request_count += 1
                self.calls.append((endpoint, params or {}))
                if "statusId" in (params or {}) or "hasOdds" in (params or {}):
                    return [
                        {
                            "fixtureId": "sundsvall-sandviken",
                            "tournamentId": 46,
                            "startTime": "2026-05-30T13:00:00Z",
                            "participant1Name": "GIF Sundsvall",
                            "participant2Name": "Sandvikens IF",
                        }
                    ]
                return [
                    {
                        "fixtureId": "osters-norrby",
                        "tournamentId": 46,
                        "startTime": "2026-05-30T15:00:00Z",
                        "participant1Name": "Osters IF",
                        "participant2Name": "Norrby IF",
                    }
                ]
            return super().get(endpoint, params)

    raw_client = FilteredFixtureMissClient()
    client = OddsPapiSyncClient(raw_client)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    fixture_calls = [
        params for endpoint, params in raw_client.calls if endpoint == "fixtures"
    ]
    historical_calls = [
        params for endpoint, params in raw_client.calls if endpoint == "historical-odds"
    ]
    assert result.matched_count == 1
    assert source_match.source_fixture_id == "osters-norrby"
    assert source_match.match_confidence == Decimal("1.0000")
    assert fixture_calls[0]["statusId"] == 2
    assert fixture_calls[0]["hasOdds"] is True
    assert "statusId" not in fixture_calls[1]
    assert "hasOdds" not in fixture_calls[1]
    assert {call.get("fixtureId") for call in historical_calls} == {"osters-norrby"}


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


def test_run_oddspapi_sync_for_session_retries_historical_odds_timeout_once(
    session,
    monkeypatch,
):
    timeout_match = _match(
        session,
        source_match_id="timeout",
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
                match_id=timeout_match.id,
                source_name="oddspapi",
                source_fixture_id="timeout-fixture",
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
    client = OddsPapiSyncClient(raw_client)
    submitted_fixture_ids = []

    class FakeFuture:
        def __init__(self, fixture_id):
            self.fixture_id = fixture_id

        def cancel(self):
            return True

        def result(self, timeout):
            if self.fixture_id == "timeout-fixture":
                raise FutureTimeoutError()
            return raw_client.get(
                "historical-odds",
                {
                    "sportId": oddspapi_sync_runner.SOCCER_SPORT_ID,
                    "fixtureId": self.fixture_id,
                    "bookmakers": oddspapi_sync_runner.SELECTED_BOOKMAKERS,
                },
            )

    class FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers
            self.shutdown_calls = []

        def submit(self, func):
            fixture_id = func.fixture_id
            submitted_fixture_ids.append(fixture_id)
            return FakeFuture(fixture_id)

        def shutdown(self, wait=True, cancel_futures=False):
            self.shutdown_calls.append((wait, cancel_futures))

    monkeypatch.setattr(oddspapi_sync_runner, "ThreadPoolExecutor", FakeExecutor, raising=False)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=timeout_match.id).one()
    assert submitted_fixture_ids == [
        "timeout-fixture",
        "timeout-fixture",
        "oddspapi-fixture-1",
    ]
    assert result.processed_match_count == 1
    assert result.failed_match_count == 1
    assert source_match.historical_odds_status == "failed"
    assert "timed out after 2 attempts" in source_match.historical_odds_error
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


def test_run_oddspapi_sync_for_session_marks_429_odds_error_as_retryable_failed(
    session,
    monkeypatch,
):
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
    client = OddsPapiSyncClient(raw_client, historical_odds_rate_limit_backoff_seconds=7)
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

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
    assert sleeps == [7]


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
    assert any("mode=full_raw_compact_neighbors" in message for message in messages)


def test_run_oddspapi_sync_for_session_marks_all_empty_outcomes_with_429_as_failed(
    session,
    monkeypatch,
):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="empty-rate-limited-fixture",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()

    class RateLimitedFullHistoricalOddsClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            self.request_count += 1
            self.calls.append((endpoint, params or {}))
            if endpoint == "markets":
                return super().get(endpoint, params)
            if endpoint == "historical-odds":
                raise OddsPapiApiError("OddsPapi HTTP error: status=429")
            return super().get(endpoint, params)

    raw_client = RateLimitedFullHistoricalOddsClient()
    client = OddsPapiSyncClient(raw_client, historical_odds_rate_limit_backoff_seconds=7)
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    assert result.failed_match_count == 1
    assert result.processed_match_count == 0
    assert source_match.historical_odds_status == "failed"
    assert source_match.historical_odds_error == "OddsPapi HTTP error: status=429"
    assert sleeps == [7]
    historical_calls = [
        params
        for endpoint, params in raw_client.calls
        if endpoint == "historical-odds"
    ]
    assert len(historical_calls) == 1
    assert "outcomeId" not in historical_calls[0]


def test_run_oddspapi_sync_for_session_rematches_blank_cached_fixture_id(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("0.0000"),
            match_reason="reset after alias update",
            historical_odds_status=None,
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

    source_match = session.query(OddsSourceMatch).filter_by(match_id=match.id).one()
    historical_calls = [
        params
        for endpoint, params in raw_client.calls
        if endpoint == "historical-odds"
    ]
    assert result.inserted_snapshot_count == 4
    assert source_match.source_fixture_id == "oddspapi-fixture-1"
    assert {call.get("fixtureId") for call in historical_calls} == {"oddspapi-fixture-1"}


def test_run_oddspapi_sync_for_session_fetches_full_history_without_outcome_id(session):
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

    historical_calls = [
        params
        for endpoint, params in raw_client.calls
        if endpoint == "historical-odds"
    ]
    assert result.inserted_snapshot_count == 4
    assert len(historical_calls) == 1
    assert "outcomeId" not in historical_calls[0]


def test_run_oddspapi_sync_for_session_stores_main_snapshots_and_raw_neighbor_summary(session):
    match = _match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name="oddspapi",
            source_fixture_id="multi-line-fixture",
            matched_at=datetime(2026, 5, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            match_confidence=Decimal("1.0000"),
            match_reason="cached",
        )
    )
    session.commit()

    class MultiLineClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            if endpoint == "markets":
                self.request_count += 1
                self.calls.append((endpoint, params or {}))
                return [
                    {
                        "marketId": 10170,
                        "marketName": "Over Under 3.00",
                        "marketType": "totals",
                        "period": "fulltime",
                        "handicap": 3.0,
                        "outcomes": [
                            {"outcomeId": 10170, "outcomeName": "Over"},
                            {"outcomeId": 10171, "outcomeName": "Under"},
                        ],
                    },
                    {
                        "marketId": 10180,
                        "marketName": "Over Under 3.25",
                        "marketType": "totals",
                        "period": "fulltime",
                        "handicap": 3.25,
                        "outcomes": [
                            {"outcomeId": 10180, "outcomeName": "Over"},
                            {"outcomeId": 10181, "outcomeName": "Under"},
                        ],
                    },
                    {
                        "marketId": 10190,
                        "marketName": "Over Under 3.50",
                        "marketType": "totals",
                        "period": "fulltime",
                        "handicap": 3.5,
                        "outcomes": [
                            {"outcomeId": 10190, "outcomeName": "Over"},
                            {"outcomeId": 10191, "outcomeName": "Under"},
                        ],
                    },
                ]
            if endpoint == "historical-odds":
                self.request_count += 1
                self.calls.append((endpoint, params or {}))
                return {
                    "fixtureId": "multi-line-fixture",
                    "bookmakers": {
                        "pinnacle": {
                            "markets": {
                                market_id: {
                                    "outcomes": {
                                        over_id: {"players": {"0": [{"createdAt": "2026-05-23T18:00:00Z", "price": over_price}]}},
                                        under_id: {"players": {"0": [{"createdAt": "2026-05-23T18:00:00Z", "price": under_price}]}},
                                    }
                                }
                                for market_id, over_id, under_id, over_price, under_price in [
                                    ("10170", "10170", "10171", 1.65, 2.30),
                                    ("10180", "10180", "10181", 1.95, 1.95),
                                    ("10190", "10190", "10191", 2.30, 1.65),
                                ]
                            }
                        }
                    },
                }
            return super().get(endpoint, params)

    client = OddsPapiSyncClient(MultiLineClient())

    result = run_oddspapi_sync_for_session(
        session=session,
        client=client,
        season=2025,
        max_matches=20,
    )

    main_lines = {
        row.market_line
        for row in session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match.id)
        .all()
    }
    raw_lines = {
        row.market_line
        for row in session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.match_id == match.id)
        .all()
    }
    assert result.inserted_snapshot_count == 2
    assert main_lines == {Decimal("3.25")}
    assert raw_lines == {Decimal("3.00"), Decimal("3.25"), Decimal("3.50")}


def test_run_oddspapi_sync_for_session_reuses_market_definitions_for_multiple_matches(session):
    GLOBAL_MARKET_DEFINITIONS_CACHE.clear()
    first = _match(
        session,
        source_match_id="first",
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    second_home = Team(canonical_name="Second Home")
    second_away = Team(canonical_name="Second Away")
    session.add_all([second_home, second_away])
    session.flush()
    second = Match(
        league=first.league,
        home_team=second_home,
        away_team=second_away,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        home_score=1,
        away_score=1,
        source_name="api_football",
        source_match_id="second",
    )
    session.add(second)
    session.flush()
    for match in [first, second]:
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=f"oddspapi-fixture-{match.source_match_id}",
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

    market_calls = [
        params
        for endpoint, params in raw_client.calls
        if endpoint == "markets"
    ]
    assert result.processed_match_count == 2
    assert result.inserted_snapshot_count == 8
    assert len(market_calls) == 1


def test_oddspapi_sync_client_reuses_global_market_definitions_cache():
    GLOBAL_MARKET_DEFINITIONS_CACHE.clear()
    first_raw_client = FakeOddsPapiClient()
    second_raw_client = FakeOddsPapiClient()
    first_client = OddsPapiSyncClient(first_raw_client)
    second_client = OddsPapiSyncClient(second_raw_client)

    first_client.fetch_markets("oddspapi-fixture-1")
    second_client.fetch_markets("oddspapi-fixture-2")

    assert [call[0] for call in first_raw_client.calls] == ["markets"]
    assert second_raw_client.calls == []


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


def test_run_oddspapi_sync_for_session_reports_diagnostic_boundaries(session):
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

    assert any("fixture_lookup_start" in message for message in messages)
    assert any("fixture_lookup_done" in message for message in messages)
    assert any("fixture_match_done" in message for message in messages)
    assert any("markets_request_start" in message for message in messages)
    assert any("markets_request_done" in message for message in messages)
    assert any("historical_odds_request_start" in message for message in messages)
    assert any("historical_odds_request_done" in message for message in messages)
    assert any("store_main_done" in message for message in messages)
    assert any("store_raw_done" in message for message in messages)
    assert any("elapsed=" in message for message in messages)


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


def test_oddspapi_sync_client_retries_fixture_lookup_without_status_filter_after_404():
    class FixtureFallbackClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            if endpoint == "fixtures" and (params or {}).get("statusId") == 2:
                self.request_count += 1
                self.calls.append((endpoint, params or {}))
                raise OddsPapiApiError("OddsPapi HTTP error: status=404", status_code=404)
            return super().get(endpoint, params)

    raw_client = FixtureFallbackClient()
    client = OddsPapiSyncClient(raw_client)

    fixtures = client.fetch_fixtures(
        tournament_id=8,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert fixtures[0].fixture_id == "oddspapi-fixture-1"
    assert raw_client.calls[0][1]["statusId"] == 2
    assert raw_client.calls[0][1]["hasOdds"] is True
    assert "statusId" not in raw_client.calls[1][1]
    assert "hasOdds" not in raw_client.calls[1][1]


def test_oddspapi_sync_client_respects_fixture_cooldown_before_404_fallback(monkeypatch):
    class FixtureFallbackClient(FakeOddsPapiClient):
        def get(self, endpoint, params=None):
            if endpoint == "fixtures" and (params or {}).get("statusId") == 2:
                self.request_count += 1
                self.calls.append((endpoint, params or {}))
                raise OddsPapiApiError("OddsPapi HTTP error: status=404", status_code=404)
            return super().get(endpoint, params)

    raw_client = FixtureFallbackClient()
    client = OddsPapiSyncClient(raw_client)
    now_values = iter([100.0, 100.0, 101.0, 107.5])
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "monotonic", lambda: next(now_values))
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    fixtures = client.fetch_fixtures(
        tournament_id=8,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert fixtures[0].fixture_id == "oddspapi-fixture-1"
    assert sleeps == [6.5]


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


def test_oddspapi_sync_client_can_share_historical_odds_limiter(monkeypatch):
    first_raw_client = FakeOddsPapiClient()
    second_raw_client = FakeOddsPapiClient()
    limiter = OddsPapiRequestLimiter(cooldown_seconds=5)
    first_client = OddsPapiSyncClient(first_raw_client, historical_odds_limiter=limiter)
    second_client = OddsPapiSyncClient(second_raw_client, historical_odds_limiter=limiter)
    now_values = iter([100.0, 100.0, 100.0, 101.0, 105.0, 105.0])
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "monotonic", lambda: next(now_values))
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    first_client.fetch_historical_odds(source_fixture_id="oddspapi-fixture-1", outcome_id="1070")
    second_client.fetch_historical_odds(source_fixture_id="oddspapi-fixture-1", outcome_id="1071")

    assert sleeps == [4.0]


def test_oddspapi_sync_client_can_share_fixture_limiter(monkeypatch):
    first_raw_client = FakeOddsPapiClient()
    second_raw_client = FakeOddsPapiClient()
    limiter = OddsPapiRequestLimiter(cooldown_seconds=7.5)
    first_client = OddsPapiSyncClient(first_raw_client, fixture_limiter=limiter)
    second_client = OddsPapiSyncClient(second_raw_client, fixture_limiter=limiter)
    now_values = iter([100.0, 100.0, 101.0, 107.5])
    sleeps = []
    monkeypatch.setattr(oddspapi_sync_runner.time, "monotonic", lambda: next(now_values))
    monkeypatch.setattr(oddspapi_sync_runner.time, "sleep", sleeps.append)

    first_client.fetch_fixtures(
        tournament_id=8,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    second_client.fetch_fixtures(
        tournament_id=8,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert sleeps == [6.5]


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

    assert sleeps == [6.5]

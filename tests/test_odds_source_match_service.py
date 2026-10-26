from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from icewine_prediction.models import League, Match, Team
from icewine_prediction.odds_source_match_service import (
    ExternalAliasInput,
    OddsPapiFixture,
    find_best_odds_source_match,
    normalize_team_name,
)


def _match(session, league_name="La Liga", home="Mallorca", away="Oviedo"):
    league = League(
        name=league_name,
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
    )
    home_team = Team(canonical_name=home)
    away_team = Team(canonical_name=away)
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="1391195",
    )
    session.add(match)
    session.commit()
    return match


def test_normalize_team_name_removes_common_suffixes_and_punctuation():
    assert normalize_team_name("RCD Mallorca") == "mallorca"
    assert normalize_team_name("Real Oviedo FC") == "real oviedo"
    assert normalize_team_name("Deportivo Alavés") == "deportivo alaves"


@pytest.mark.parametrize(
    "league_round,kickoff,expected",
    [
        ("Apertura - 14", datetime(2026, 10, 26, 9), 27464),
        ("Clausura - Final", datetime(2026, 5, 25, 9), 27466),
        ("Apertura - Final", datetime(2027, 1, 5, 9), 27464),
        ("Clausura - 7", datetime(2026, 7, 5, 9), 27466),
        (None, datetime(2026, 10, 26, 9), 27464),
        (None, datetime(2026, 5, 25, 9), 27466),
        (None, datetime(2026, 7, 1, 4, tzinfo=ZoneInfo("UTC")), 27466),
        (None, datetime(2026, 7, 1, 8, tzinfo=ZoneInfo("UTC")), 27464),
    ],
)
def test_mexico_matching_selects_competition_phase(session, league_round, kickoff, expected):
    match = _match(session)
    match.league.source_league_id = "262"
    match.league_round = league_round
    match.kickoff_time = kickoff
    utc = kickoff.replace(tzinfo=ZoneInfo("Asia/Shanghai")) if kickoff.tzinfo is None else kickoff
    fixtures = [
        OddsPapiFixture(str(tid), tid, utc.astimezone(ZoneInfo("UTC")), "Mallorca", "Oviedo")
        for tid in (27466, 27464)
    ]
    result = find_best_odds_source_match(match, fixtures, {"262": 27466})
    assert result is not None
    assert result.fixture.tournament_id == expected


def test_find_best_odds_source_match_matches_league_time_and_team_names(session):
    match = _match(session)
    fixtures = [
        OddsPapiFixture(
            fixture_id="wrong-team",
            tournament_id=8,
            start_time=datetime(2026, 5, 23, 19, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="Getafe CF",
            away_team_name="CA Osasuna",
        ),
        OddsPapiFixture(
            fixture_id="expected",
            tournament_id=8,
            start_time=datetime(2026, 5, 23, 19, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="RCD Mallorca",
            away_team_name="Real Oviedo",
        ),
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"140": 8},
    )

    assert result is not None
    assert result.fixture.fixture_id == "expected"
    assert result.confidence == 1
    assert "team" in result.reason


def test_find_best_odds_source_match_rejects_wrong_tournament(session):
    match = _match(session)
    fixtures = [
        OddsPapiFixture(
            fixture_id="serie-a",
            tournament_id=23,
            start_time=datetime(2026, 5, 23, 19, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="RCD Mallorca",
            away_team_name="Real Oviedo",
        )
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"140": 8},
    )

    assert result is None


def test_find_best_odds_source_match_rejects_only_weak_shared_tokens(session):
    match = _match(
        session,
        league_name="Saudi Pro League",
        home="Al-Hazm",
        away="Al Taawon",
    )
    match.league.source_league_id = "307"
    match.kickoff_time = datetime(2026, 5, 22, 2, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    fixtures = [
        OddsPapiFixture(
            fixture_id="wrong-al-overlap",
            tournament_id=955,
            start_time=datetime(2026, 5, 21, 18, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="Al-Ittihad Club",
            away_team_name="Al Qadsiah",
        )
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"307": 955},
    )

    assert result is None


def test_find_best_odds_source_match_rejects_time_outside_window(session):
    match = _match(session)
    fixtures = [
        OddsPapiFixture(
            fixture_id="too-early",
            tournament_id=8,
            start_time=datetime(2026, 5, 23, 10, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="RCD Mallorca",
            away_team_name="Real Oviedo",
        )
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"140": 8},
    )

    assert result is None


def test_find_best_odds_source_match_handles_naive_local_kickoff_time(session):
    match = _match(session)
    match.kickoff_time = datetime(2026, 5, 24, 3, 0)
    fixtures = [
        OddsPapiFixture(
            fixture_id="expected",
            tournament_id=8,
            start_time=datetime(2026, 5, 23, 19, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="RCD Mallorca",
            away_team_name="Real Oviedo",
        )
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"140": 8},
    )

    assert result is not None
    assert result.fixture.fixture_id == "expected"


def test_find_best_odds_source_match_uses_external_team_aliases(session):
    match = _match(session, league_name="Premier League", home="Wolves", away="Fulham")
    match.league.source_league_id = "39"
    match.kickoff_time = datetime(2026, 5, 17, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    fixtures = [
        OddsPapiFixture(
            fixture_id="wolves-fulham",
            tournament_id=1,
            start_time=datetime(2026, 5, 17, 14, 0, tzinfo=ZoneInfo("UTC")),
            home_team_name="Wolverhampton Wanderers",
            away_team_name="Fulham FC",
        )
    ]

    result = find_best_odds_source_match(
        match,
        fixtures,
        api_football_to_oddspapi_tournament_ids={"39": 1},
        team_aliases=[
            ExternalAliasInput(
                canonical_name="Wolves",
                alias_name="Wolverhampton Wanderers",
            )
        ],
    )

    assert result is not None
    assert result.fixture.fixture_id == "wolves-fulham"
    assert result.confidence == 1

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, Team
from icewine_prediction.oddspapi_diagnostic_service import (
    run_oddspapi_fixture_diagnostics_for_session,
)
from icewine_prediction.oddspapi_sync_runner import OddsPapiSyncClient


class FakeOddsPapiFixtureClient:
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.request_count = 0
        self.calls = []

    def get(self, endpoint, params=None):
        self.request_count += 1
        self.calls.append((endpoint, params or {}))
        if endpoint != "fixtures":
            raise AssertionError(f"unexpected endpoint: {endpoint}")
        return self.fixtures


def _finished_match(
    session,
    home_team_name="Mallorca",
    away_team_name="Oviedo",
    kickoff_time=None,
):
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
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
        source_match_id="1391195",
    )
    session.add(match)
    session.commit()
    return match


def test_fixture_diagnostics_records_same_kickoff_candidates_and_best_match(
    session,
    tmp_path,
):
    match = _finished_match(session)
    raw_client = FakeOddsPapiFixtureClient(
        [
            {
                "fixtureId": "oddspapi-getafe-osasuna",
                "tournamentId": 8,
                "startTime": "2026-05-23T19:00:00Z",
                "participant1Name": "Getafe CF",
                "participant2Name": "Osasuna",
            },
            {
                "fixtureId": "oddspapi-mallorca-oviedo",
                "tournamentId": 8,
                "startTime": "2026-05-23T19:00:00Z",
                "participant1Name": "RCD Mallorca",
                "participant2Name": "Real Oviedo",
            },
        ]
    )

    report = run_oddspapi_fixture_diagnostics_for_session(
        session=session,
        client=OddsPapiSyncClient(raw_client),
        season=2025,
        max_matches=1,
        request_budget=10,
        log_dir=tmp_path,
        run_id="diagnostic-test",
    )

    assert report.diagnosed_match_count == 1
    assert report.matched_count == 1
    assert report.matches[0].match_id == match.id
    assert report.matches[0].status == "matched"
    assert report.matches[0].best_fixture_id == "oddspapi-mallorca-oviedo"
    assert [candidate.fixture_id for candidate in report.matches[0].candidates] == [
        "oddspapi-mallorca-oviedo",
        "oddspapi-getafe-osasuna",
    ]
    assert raw_client.calls[0][1]["from"] == "2026-05-23T17:00:00Z"
    assert raw_client.calls[0][1]["to"] == "2026-05-23T21:00:00Z"

    run_dir = tmp_path / "diagnostic-test"
    assert (run_dir / "summary.md").exists()
    match_rows = (run_dir / "matches.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(match_rows[0])["best_fixture_id"] == "oddspapi-mallorca-oviedo"


def test_fixture_diagnostics_marks_manual_review_when_only_wrong_teams_return(
    session,
    tmp_path,
):
    _finished_match(session)
    raw_client = FakeOddsPapiFixtureClient(
        [
            {
                "fixtureId": "oddspapi-getafe-osasuna",
                "tournamentId": 8,
                "startTime": "2026-05-23T19:00:00Z",
                "participant1Name": "Getafe CF",
                "participant2Name": "Osasuna",
            }
        ]
    )

    report = run_oddspapi_fixture_diagnostics_for_session(
        session=session,
        client=OddsPapiSyncClient(raw_client),
        season=2025,
        max_matches=1,
        request_budget=10,
        log_dir=tmp_path,
        run_id="manual-review-test",
    )

    assert report.manual_review_count == 1
    assert report.matches[0].status == "manual_review"
    assert report.matches[0].candidate_count == 1
    assert "team similarity below threshold" in report.matches[0].reason

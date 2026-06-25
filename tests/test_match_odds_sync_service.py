from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.match_odds_sync_service import (
    MatchOddsSyncProvider,
    has_priority_pinnacle_historical_odds,
    run_match_odds_sync_for_session,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    THE_ODDS_API_SOURCE_NAME,
)
from icewine_prediction.the_odds_api_sync_runner import TheOddsApiSyncResult


def test_run_match_odds_sync_defaults_to_the_odds_api_and_reports_success(session):
    match = _add_match(session)
    calls = []

    def fake_the_odds_api_sync(**kwargs):
        calls.append(kwargs)
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.95"),
            )
        )
        session.commit()
        return TheOddsApiSyncResult(
            processed_match_count=1,
            matched_count=1,
            failed_match_count=0,
            inserted_snapshot_count=1,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=1,
            total_goals_count=0,
            match_winner_count=0,
            requests_used=3,
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    assert calls
    assert calls[0]["match_ids"] == {match.id}
    assert result == {
        "success": [{"match_id": match.id, "message": "赔率已刷新"}],
        "failed": [],
        "skipped": [],
        "requests": 3,
    }


def test_run_match_odds_sync_does_not_overwrite_legacy_oddspapi_snapshots(session):
    match = _add_match(session)
    session.add(_snapshot(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90")))
    session.commit()

    def fake_the_odds_api_sync(**kwargs):
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.95"),
            )
        )
        session.commit()
        return TheOddsApiSyncResult(
            processed_match_count=1,
            matched_count=1,
            failed_match_count=0,
            inserted_snapshot_count=1,
            skipped_duplicate_snapshot_count=0,
            skipped_existing_odds_count=0,
            asian_handicap_count=1,
            total_goals_count=0,
            match_winner_count=0,
            requests_used=1,
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    snapshots = session.query(HistoricalOddsSnapshot).order_by(HistoricalOddsSnapshot.source_name).all()
    assert [snapshot.source_name for snapshot in snapshots] == [
        ODDSPAPI_SOURCE_NAME,
        THE_ODDS_API_SOURCE_NAME,
    ]
    assert result["success"] == [{"match_id": match.id, "message": "赔率已刷新"}]


def test_has_priority_pinnacle_historical_odds_accepts_legacy_source(session):
    match = _add_match(session)
    session.add(_snapshot(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90")))
    session.commit()

    assert has_priority_pinnacle_historical_odds(session, match.id) is True


def test_run_match_odds_sync_supports_explicit_legacy_provider(session):
    match = _add_match(session)
    calls = []

    def fake_legacy_sync(**kwargs):
        calls.append(kwargs)
        session.add(_snapshot(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90")))
        session.commit()
        return type("LegacyResult", (), {"requests_used": 4})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        provider=MatchOddsSyncProvider.ODDSPAPI,
        oddspapi_syncer=fake_legacy_sync,
    )

    assert calls
    assert result["requests"] == 4
    assert result["success"] == [{"match_id": match.id, "message": "赔率已刷新"}]


def _add_match(session, *, season: int | None = 2026) -> Match:
    league = League(
        name="Premier League",
        country_or_region="England",
        level=1,
        is_enabled=True,
        source_name="api_football",
        source_league_id="39",
    )
    home = Team(canonical_name="Arsenal")
    away = Team(canonical_name="Chelsea")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 26, 19, 0, tzinfo=ZoneInfo("UTC")),
        season=season,
        status="scheduled",
        source_name="api_football",
        source_match_id="1001",
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(
    *,
    match_id: int,
    source_name: str,
    odds: Decimal,
    bookmaker: str = "pinnacle",
) -> HistoricalOddsSnapshot:
    return HistoricalOddsSnapshot(
        match_id=match_id,
        source_name=source_name,
        source_fixture_id=f"{source_name}-event",
        bookmaker=bookmaker,
        market_type="asian_handicap",
        market_id=f"{source_name}:asian_handicap:-0.25:home",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 6, 26, 18, 50, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )

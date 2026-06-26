from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.match_odds_sync_service import (
    MatchOddsSyncProvider,
    has_trusted_historical_odds,
    run_match_odds_sync_for_session,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    THE_ODDS_API_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
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
        return _the_odds_api_result(
            requests_used=3,
            credits_used=90,
            inserted_snapshot_count=1,
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    assert calls
    assert calls[0]["match_ids"] == {match.id}
    assert _success_match_ids(result) == [match.id]
    assert result["failed"] == []
    assert result["skipped"] == []
    assert result["requests"] == 3
    assert result["credits"] == 90


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
        return _the_odds_api_result(requests_used=1, credits_used=30, inserted_snapshot_count=1)

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
    assert _success_match_ids(result) == [match.id]


def test_has_trusted_historical_odds_accepts_legacy_source(session):
    match = _add_match(session)
    session.add(_snapshot(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME, odds=Decimal("1.90")))
    session.commit()

    assert has_trusted_historical_odds(session, match.id) is True


def test_has_trusted_historical_odds_accepts_sbobet_fallback(session):
    match = _add_match(session)
    session.add(
        _snapshot(
            match_id=match.id,
            source_name=ODDSPAPI_SOURCE_NAME,
            bookmaker="sbobet",
            odds=Decimal("1.90"),
        )
    )
    session.commit()

    assert has_trusted_historical_odds(session, match.id) is True


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
    assert _success_match_ids(result) == [match.id]


def test_run_match_odds_sync_falls_back_to_sbobet_for_verified_fallback_league(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild",
        country_or_region="Iceland",
        source_league_id="164",
    )
    the_odds_api_calls = []
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        the_odds_api_calls.append(kwargs)
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                bookmaker="sbobet",
                odds=Decimal("1.90"),
            )
        )
        session.commit()
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
    )

    assert the_odds_api_calls
    assert oddspapi_calls
    assert oddspapi_calls[0]["match_ids"] == {match.id}
    assert oddspapi_calls[0]["bookmaker"] == "sbobet"
    assert result["requests"] == 7
    assert result["credits"] == 60
    assert _success_match_ids(result) == [match.id]


def test_run_match_odds_sync_does_not_fallback_to_sbobet_for_non_fallback_league(session):
    match = _add_match(session)
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
    )

    assert oddspapi_calls == []
    assert result["requests"] == 2
    assert result["credits"] == 60
    assert _success_match_ids(result) == []
    assert [item["match_id"] for item in result["failed"]] == [match.id]


def test_run_match_odds_sync_falls_back_to_zqcf918_before_sbobet(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild",
        country_or_region="Iceland",
        source_league_id="164",
    )
    zqcf918_calls = []
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_zqcf918_sync(**kwargs):
        zqcf918_calls.append(kwargs)
        session.add(_snapshot(match_id=match.id, source_name=ZQCF918_SOURCE_NAME, odds=Decimal("1.91")))
        session.commit()
        return {"success": [{"match_id": match.id}], "failed": [], "skipped": [], "requests": 3, "credits": 0}

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert zqcf918_calls
    assert zqcf918_calls[0]["match_ids"] == {match.id}
    assert oddspapi_calls == []
    assert result["requests"] == 5
    assert result["credits"] == 60
    assert _success_match_ids(result) == [match.id]


def test_run_match_odds_sync_uses_sbobet_when_zqcf918_has_no_odds(session):
    match = _add_match(
        session,
        league_name="Urvalsdeild",
        country_or_region="Iceland",
        source_league_id="164",
    )
    oddspapi_calls = []

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_zqcf918_sync(**kwargs):
        return {
            "success": [],
            "failed": [{"match_id": match.id, "message": "empty"}],
            "skipped": [],
            "requests": 3,
            "credits": 0,
        }

    def fake_oddspapi_sync(**kwargs):
        oddspapi_calls.append(kwargs)
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                bookmaker="sbobet",
                odds=Decimal("1.90"),
            )
        )
        session.commit()
        return type("FallbackResult", (), {"requests_used": 5})()

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        oddspapi_syncer=fake_oddspapi_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert oddspapi_calls
    assert oddspapi_calls[0]["bookmaker"] == "sbobet"
    assert result["requests"] == 10
    assert _success_match_ids(result) == [match.id]


def _add_match(
    session,
    *,
    season: int | None = 2026,
    league_name: str = "Premier League",
    country_or_region: str = "England",
    source_league_id: str = "39",
) -> Match:
    league = League(
        name=league_name,
        country_or_region=country_or_region,
        level=1,
        is_enabled=True,
        source_name="api_football",
        source_league_id=source_league_id,
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
        market_id=f"{source_name}:{bookmaker}:asian_handicap:-0.25:home",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 6, 26, 18, 50, tzinfo=ZoneInfo("UTC")),
        period="full_time",
    )


def _the_odds_api_result(
    *,
    requests_used: int,
    inserted_snapshot_count: int,
    credits_used: int = 0,
) -> TheOddsApiSyncResult:
    return TheOddsApiSyncResult(
        processed_match_count=1,
        matched_count=1 if inserted_snapshot_count else 0,
        failed_match_count=0,
        inserted_snapshot_count=inserted_snapshot_count,
        skipped_duplicate_snapshot_count=0,
        skipped_existing_odds_count=0,
        asian_handicap_count=inserted_snapshot_count,
        total_goals_count=0,
        match_winner_count=0,
        requests_used=requests_used,
        credits_used=credits_used,
    )


def _success_match_ids(result) -> list[int]:
    return [item["match_id"] for item in result["success"]]

import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.match_odds_sync_service import (
    MatchOddsSyncProvider,
    has_trusted_historical_odds,
    run_match_odds_sync_for_session,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch, Team
from icewine_prediction.odds_provider_selection_service import (
    ODDSPAPI_SOURCE_NAME,
    THE_ODDS_API_SOURCE_NAME,
    ZQCF918_SOURCE_NAME,
)
from icewine_prediction.sources.the_odds_api_client import TheOddsApiRecoveryBudget
from icewine_prediction.the_odds_api_sync_runner import (
    TheOddsApiMatchSyncResult,
    TheOddsApiSyncClient,
    TheOddsApiSyncResult,
    run_the_odds_api_sync_for_session,
)


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


def test_run_match_odds_sync_preserves_the_odds_api_primary_failure_reason(session):
    match = _add_match(session)

    def fake_the_odds_api_sync(**kwargs):
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                source_fixture_id="unmatched-event",
                matched_at=datetime(2026, 6, 26, 18, 50, tzinfo=ZoneInfo("UTC")),
                match_confidence=Decimal("0.0000"),
                match_reason="no team match",
                historical_odds_status="unmatched",
                historical_odds_error="no matching The Odds API event",
            )
        )
        session.commit()
        return _the_odds_api_result(requests_used=2, credits_used=60, inserted_snapshot_count=0)

    def fake_zqcf918_sync(**kwargs):
        return {
            "success": [],
            "failed": [],
            "skipped": [{"match_id": match.id, "message": "missing zqcf918 match ID"}],
            "requests": 0,
            "credits": 0,
        }

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert _success_match_ids(result) == []
    assert result["failed"] == [
        {
            "match_id": match.id,
            "message": (
                "The Odds API unmatched: no matching The Odds API event; "
                "fallback: missing zqcf918 match ID"
            ),
            "source": THE_ODDS_API_SOURCE_NAME,
            "error_code": "unmatched",
            "failure_stage": "fallback",
            "attempt_count": 1,
            "retry_exhausted": False,
            "fallback_error": "missing zqcf918 match ID",
            "primary_refresh_status": "failed",
            "primary_refresh_error": "unmatched",
        }
    ]


def test_run_match_odds_sync_shares_trace_and_recovery_budget_across_seasons(session):
    first = _add_match(session, season=2025)
    second = _add_match(
        session,
        season=2026,
        league_name="Allsvenskan",
        country_or_region="Sweden",
        source_league_id="113",
        home_team_name="Tottenham",
        away_team_name="Everton",
        source_match_id="1002",
    )
    calls = []

    def fake_the_odds_api_sync(**kwargs):
        calls.append(kwargs)
        kwargs["recovery_budget"].add_limiter_wait(1.0)
        match_id = next(iter(kwargs["match_ids"]))
        session.add(
            _snapshot(
                match_id=match_id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.95"),
            )
        )
        session.commit()
        return _the_odds_api_result(
            requests_used=len(calls),
            credits_used=len(calls) * 10,
            inserted_snapshot_count=1,
            match_results=(
                TheOddsApiMatchSyncResult(
                    match_id=match_id,
                    status="success",
                    attempt_count=2 if len(calls) == 1 else 1,
                ),
            ),
            trace_id=kwargs["trace_id"],
            retry_count=1,
            retry_success_count=1,
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[first.id, second.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    assert len(calls) == 2
    assert calls[0]["trace_id"] == calls[1]["trace_id"] == result["trace_id"]
    assert calls[0]["recovery_budget"] is calls[1]["recovery_budget"]
    assert _success_match_ids(result) == [first.id, second.id]
    assert result["requests"] == 3
    assert result["credits"] == 30
    assert result["retry_count"] == 2
    assert result["retry_success_count"] == 2
    assert result["retry_recovered_match_count"] == 1
    assert result["rate_limit_wait_seconds"] == 2.0
    assert result["recovery_elapsed_seconds"] == 2.0
    assert result["recovery_budget_remaining_seconds"] == 118.0


def test_run_match_odds_sync_merges_per_match_primary_status_without_spreading_batch_error(
    session,
    caplog,
):
    caplog.set_level(logging.INFO)
    first = _add_match(session)
    second = _add_match(
        session,
        league_name="Allsvenskan",
        country_or_region="Sweden",
        source_league_id="113",
        home_team_name="Tottenham",
        away_team_name="Everton",
        source_match_id="1002",
    )

    def fake_the_odds_api_sync(**kwargs):
        session.add(
            _snapshot(
                match_id=second.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.95"),
            )
        )
        session.commit()
        return _the_odds_api_result(
            requests_used=3,
            inserted_snapshot_count=1,
            match_results=(
                TheOddsApiMatchSyncResult(
                    match_id=first.id,
                    status="failed",
                    error_message="current odds request timed out",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                ),
                TheOddsApiMatchSyncResult(match_id=second.id, status="success"),
            ),
            error_message="season request reported a failure",
            trace_id=kwargs["trace_id"],
            retry_count=1,
        )

    def fake_zqcf918_sync(**kwargs):
        assert kwargs["match_ids"] == {first.id}
        return {
            "success": [],
            "failed": [],
            "skipped": [{"match_id": first.id, "message": "missing zqcf918 odds"}],
            "requests": 0,
            "credits": 0,
        }

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[first.id, second.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert _success_match_ids(result) == [second.id]
    assert [item["match_id"] for item in result["failed"]] == [first.id]
    assert result["failed"][0]["error_code"] == "read_timeout"
    assert result["failed"][0]["attempt_count"] == 2
    assert result["failed"][0]["retry_exhausted"] is True
    assert result["odds_status"] == "partial"
    assert result["success"][0]["primary_refresh_status"] == "success"
    assert result["success"][0]["primary_refresh_error"] is None
    messages = [record.getMessage() for record in caplog.records]
    assert (
        "match_odds_sync_result "
        f"trace_id={result['trace_id']} match_id={first.id} status=failed "
        "primary_refresh_status=failed failure_stage=fallback"
    ) in messages
    assert sum(message.startswith("match_odds_sync_result") for message in messages) == 2


def test_run_match_odds_sync_keeps_raised_provider_error_at_batch_level(session):
    first = _add_match(session)
    second = _add_match(
        session,
        league_name="Allsvenskan",
        country_or_region="Sweden",
        source_league_id="113",
        home_team_name="Tottenham",
        away_team_name="Everton",
        source_match_id="1002",
    )

    def fake_the_odds_api_sync(**kwargs):
        raise RuntimeError("global boom")

    def fake_zqcf918_sync(**kwargs):
        assert kwargs["match_ids"] == {first.id, second.id}
        session.add(
            _snapshot(
                match_id=first.id,
                source_name=ZQCF918_SOURCE_NAME,
                odds=Decimal("1.91"),
            )
        )
        session.commit()
        return {
            "success": [{"match_id": first.id}],
            "failed": [{"match_id": second.id, "message": "fallback empty"}],
            "skipped": [],
            "requests": 1,
            "credits": 0,
        }

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[first.id, second.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
        zqcf918_syncer=fake_zqcf918_sync,
    )

    assert _success_match_ids(result) == [first.id]
    assert [item["match_id"] for item in result["failed"]] == [second.id]
    assert result["not_attempted"] == []
    final_items = result["success"] + result["failed"]
    assert all(item.get("primary_refresh_error") != "global boom" for item in final_items)
    assert all("global boom" not in item["message"] for item in final_items)
    assert result["error_message"] == "global boom"


def test_run_match_odds_sync_uses_existing_trusted_odds_after_primary_refresh_failure(session):
    match = _add_match(session)
    session.add(
        _snapshot(
            match_id=match.id,
            source_name=ZQCF918_SOURCE_NAME,
            odds=Decimal("1.91"),
        )
    )
    session.commit()

    def fake_the_odds_api_sync(**kwargs):
        return _the_odds_api_result(
            requests_used=2,
            inserted_snapshot_count=0,
            match_results=(
                TheOddsApiMatchSyncResult(
                    match_id=match.id,
                    status="failed",
                    error_message="current odds request timed out",
                    error_code="read_timeout",
                    attempt_count=2,
                    retry_exhausted=True,
                ),
            ),
            trace_id=kwargs["trace_id"],
            retry_count=1,
        )

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_the_odds_api_sync,
    )

    assert result["failed"] == []
    assert result["success"] == [
        {
            "match_id": match.id,
            "message": "赔率已刷新",
            "source": ZQCF918_SOURCE_NAME,
            "attempt_count": 2,
            "retried": True,
            "primary_refresh_status": "failed_existing_odds_used",
            "primary_refresh_error": "read_timeout",
        }
    ]


def test_legacy_sync_new_snapshot_wins_over_unchanged_stale_source_failure(session):
    match = _add_match(session)
    session.add(
        OddsSourceMatch(
            match_id=match.id,
            source_name=THE_ODDS_API_SOURCE_NAME,
            source_fixture_id="stale-event",
            matched_at=datetime(2026, 6, 25, 18, 50, tzinfo=ZoneInfo("UTC")),
            match_confidence=Decimal("0.5000"),
            match_reason="stale failure",
            historical_odds_status="failed",
            historical_odds_checked_at=datetime(
                2026,
                6,
                25,
                18,
                50,
                tzinfo=ZoneInfo("UTC"),
            ),
            historical_odds_error="read_timeout",
        )
    )
    session.commit()

    def fake_legacy_sync(**kwargs):
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.96"),
            )
        )
        session.commit()
        return _the_odds_api_result(
            requests_used=1,
            inserted_snapshot_count=1,
            match_results=(),
            trace_id=kwargs["trace_id"],
        )

    def unexpected_fallback(**kwargs):
        raise AssertionError("fallback must not run after a new trusted primary snapshot")

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_legacy_sync,
        zqcf918_syncer=unexpected_fallback,
    )

    assert result["failed"] == []
    assert result["success"][0]["source"] == THE_ODDS_API_SOURCE_NAME
    assert result["success"][0]["primary_refresh_status"] == "success"
    assert result["success"][0]["primary_refresh_error"] is None


def test_legacy_sync_prefers_changed_partial_source_status_over_new_snapshot_inference(session):
    match = _add_match(session)
    source_match = OddsSourceMatch(
        match_id=match.id,
        source_name=THE_ODDS_API_SOURCE_NAME,
        source_fixture_id="legacy-event",
        matched_at=datetime(2026, 6, 25, 18, 50, tzinfo=ZoneInfo("UTC")),
        match_confidence=Decimal("0.5000"),
        match_reason="old failure",
        historical_odds_status="failed",
        historical_odds_checked_at=datetime(
            2026,
            6,
            25,
            18,
            50,
            tzinfo=ZoneInfo("UTC"),
        ),
        historical_odds_error="old_error",
    )
    session.add(source_match)
    session.commit()

    def fake_legacy_sync(**kwargs):
        source_match.historical_odds_status = "partial_success"
        source_match.historical_odds_checked_at = datetime(
            2026,
            6,
            26,
            18,
            50,
            tzinfo=ZoneInfo("UTC"),
        )
        source_match.historical_odds_error = "read_timeout"
        session.add(
            _snapshot(
                match_id=match.id,
                source_name=THE_ODDS_API_SOURCE_NAME,
                odds=Decimal("1.97"),
            )
        )
        session.commit()
        return _the_odds_api_result(
            requests_used=2,
            inserted_snapshot_count=1,
            match_results=(),
            trace_id=kwargs["trace_id"],
        )

    def unexpected_fallback(**kwargs):
        raise AssertionError("fallback must not run after a new trusted primary snapshot")

    result = run_match_odds_sync_for_session(
        session=session,
        match_ids=[match.id],
        the_odds_api_syncer=fake_legacy_sync,
        zqcf918_syncer=unexpected_fallback,
    )

    assert result["failed"] == []
    assert result["success"] == [
        {
            "match_id": match.id,
            "message": "赔率已刷新",
            "source": THE_ODDS_API_SOURCE_NAME,
            "attempt_count": 1,
            "retried": False,
            "primary_refresh_status": "partial_success",
            "primary_refresh_error": "read_timeout",
        }
    ]


def test_session_runner_binds_explicit_recovery_budget_to_raw_client(session):
    class RawClient:
        request_count = 0
        credit_count = 0
        provider_requests_used = None
        provider_requests_remaining = None
        retry_count = 0
        retry_success_count = 0
        recovery_budget = TheOddsApiRecoveryBudget(limit_seconds=1.0)
        trace_id = None

    raw_client = RawClient()
    recovery_budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)

    result = run_the_odds_api_sync_for_session(
        session=session,
        client=TheOddsApiSyncClient(raw_client),
        season=2099,
        max_matches=1,
        trace_id="shared-trace",
        recovery_budget=recovery_budget,
    )

    assert raw_client.recovery_budget is recovery_budget
    assert raw_client.trace_id == "shared-trace"
    assert result.trace_id == "shared-trace"


def _add_match(
    session,
    *,
    season: int | None = 2026,
    league_name: str = "Premier League",
    country_or_region: str = "England",
    source_league_id: str = "39",
    home_team_name: str = "Arsenal",
    away_team_name: str = "Chelsea",
    source_match_id: str = "1001",
) -> Match:
    league = League(
        name=league_name,
        country_or_region=country_or_region,
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
        season=season,
        status="scheduled",
        source_name="api_football",
        source_match_id=source_match_id,
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
    match_results: tuple[TheOddsApiMatchSyncResult, ...] = (),
    not_attempted_match_ids: tuple[int, ...] = (),
    error_message: str | None = None,
    trace_id: str | None = None,
    retry_count: int = 0,
    retry_success_count: int = 0,
) -> TheOddsApiSyncResult:
    successful_statuses = {"success", "partial_success"}
    return TheOddsApiSyncResult(
        processed_match_count=sum(item.status in successful_statuses for item in match_results),
        matched_count=sum(item.status in successful_statuses for item in match_results),
        failed_match_count=sum(item.status == "failed" for item in match_results),
        inserted_snapshot_count=inserted_snapshot_count,
        skipped_duplicate_snapshot_count=0,
        skipped_existing_odds_count=0,
        asian_handicap_count=inserted_snapshot_count,
        total_goals_count=0,
        match_winner_count=0,
        requests_used=requests_used,
        credits_used=credits_used,
        error_message=error_message,
        match_results=match_results,
        not_attempted_match_ids=not_attempted_match_ids,
        trace_id=trace_id,
        retry_count=retry_count,
        retry_success_count=retry_success_count,
    )


def _success_match_ids(result) -> list[int]:
    return [item["match_id"] for item in result["success"]]

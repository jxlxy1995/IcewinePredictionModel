import logging
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot, Match, OddsSourceMatch
from icewine_prediction.execution_timepoint_coverage_service import (
    get_standard_execution_timepoint_coverage,
    has_complete_core_execution_timepoint_coverage,
)
from icewine_prediction.oddspapi_sync_runner import run_oddspapi_sync_result
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
    TRUSTED_SNAPSHOT_PRIORITY,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.the_odds_api_client import (
    TheOddsApiClient,
    TheOddsApiRecoveryBudget,
)
from icewine_prediction.the_odds_api_sync_runner import (
    TheOddsApiMatchSyncResult,
    TheOddsApiSyncClient,
    run_the_odds_api_sync_for_session,
)
from icewine_prediction.zqcf918_sync_service import run_zqcf918_sync_for_session


logger = logging.getLogger(__name__)


class MatchOddsSyncProvider(StrEnum):
    THE_ODDS_API = THE_ODDS_API_SOURCE_NAME
    ODDSPAPI = "oddspapi"


SyncResultPayload = dict[str, Any]


def run_match_odds_sync_for_session(
    *,
    session: Session,
    match_ids: list[int],
    provider: MatchOddsSyncProvider | str = MatchOddsSyncProvider.ODDSPAPI,
    the_odds_api_syncer: Callable[..., Any] | None = None,
    oddspapi_syncer: Callable[..., Any] = run_oddspapi_sync_result,
    zqcf918_syncer: Callable[..., Any] = run_zqcf918_sync_for_session,
    oddspapi_enabled: bool = True,
) -> SyncResultPayload:
    trace_id = uuid4().hex[:12]
    recovery_budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)
    requested_match_ids = list(dict.fromkeys(match_ids))
    if not requested_match_ids:
        return _finalize_sync_result(
            trace_id=trace_id,
            recovery_budget=recovery_budget,
            success=[],
            failed=[],
            skipped=[],
            not_attempted=[],
        )

    matches = session.query(Match).filter(Match.id.in_(requested_match_ids)).all()
    matches_by_id = {match.id: match for match in matches}
    skipped = [
        {"match_id": match_id, "message": "缺少比赛"}
        for match_id in requested_match_ids
        if match_id not in matches_by_id
    ]
    skipped.extend(
        {"match_id": match.id, "message": "缺少赛季"}
        for match in matches
        if match.season is None
    )
    seasons = sorted({match.season for match in matches if match.season is not None})
    if not seasons:
        return _finalize_sync_result(
            trace_id=trace_id,
            recovery_budget=recovery_budget,
            success=[],
            failed=[],
            skipped=skipped,
            not_attempted=[],
        )

    selected_provider = MatchOddsSyncProvider(provider)
    if selected_provider == MatchOddsSyncProvider.ODDSPAPI and not oddspapi_enabled:
        selected_provider = MatchOddsSyncProvider.THE_ODDS_API
    the_odds_api_syncer = the_odds_api_syncer or run_default_the_odds_api_sync_for_session
    eligible_match_ids = {match.id for match in matches if match.season is not None}
    trusted_sources_before = {
        match_id: _trusted_snapshot_source(session, match_id)
        for match_id in eligible_match_ids
    }
    the_odds_api_snapshot_ids_before = _the_odds_api_snapshot_ids(
        session,
        eligible_match_ids,
    )
    source_match_states_before = _the_odds_api_source_match_states(
        session,
        eligible_match_ids,
    )

    requests_used = 0
    credits_used = 0
    retry_count = 0
    retry_success_count = 0
    provider_requests_used: int | None = None
    provider_requests_remaining: int | None = None
    result_rate_limit_wait_seconds = 0.0
    result_recovery_elapsed_seconds = 0.0
    result_recovery_budget_remaining_seconds = recovery_budget.limit_seconds
    primary_results: dict[int, TheOddsApiMatchSyncResult] = {}
    not_attempted_ids: set[int] = set()
    fallback_errors: dict[int, str] = {}
    fallback_invoked_ids: set[int] = set()
    fallback_attempted_ids: set[int] = set()
    batch_errors: list[str] = []

    for season in seasons:
        season_match_ids = {match.id for match in matches if match.season == season}
        unresolved_ids = set(season_match_ids)

        if selected_provider == MatchOddsSyncProvider.ODDSPAPI:
            oddspapi_result = None
            try:
                oddspapi_result = _run_provider_sync(
                    provider=MatchOddsSyncProvider.ODDSPAPI,
                    session=session,
                    season=season,
                    match_ids=unresolved_ids,
                    the_odds_api_syncer=the_odds_api_syncer,
                    oddspapi_syncer=oddspapi_syncer,
                    trace_id=trace_id,
                    recovery_budget=recovery_budget,
                )
            except Exception as exc:
                session.rollback()
                batch_errors.append(str(exc))
                oddspapi_result = type("OddspapiFailure", (), {"error_message": str(exc)})()
            requests_used += int(getattr(oddspapi_result, "requests_used", 0) or 0)
            credits_used += int(getattr(oddspapi_result, "credits_used", 0) or 0)
            _merge_oddspapi_primary_results(
                session=session,
                match_ids=unresolved_ids,
                result=oddspapi_result,
                primary_results=primary_results,
            )
            _log_standard_timepoint_coverage(session, unresolved_ids, stage="oddspapi")
            unresolved_ids = _unresolved_match_ids(session, unresolved_ids)

        if unresolved_ids and (selected_provider == MatchOddsSyncProvider.ODDSPAPI or selected_provider == MatchOddsSyncProvider.THE_ODDS_API):
            the_odds_api_ids = set(unresolved_ids)
            if selected_provider == MatchOddsSyncProvider.ODDSPAPI:
                fallback_invoked_ids.update(the_odds_api_ids)
            _log_standard_timepoint_coverage(session, the_odds_api_ids, stage="the_odds_api_before")
            result = None
            try:
                result = _run_provider_sync(
                    provider=MatchOddsSyncProvider.THE_ODDS_API,
                    session=session,
                    season=season,
                    match_ids=the_odds_api_ids,
                    the_odds_api_syncer=the_odds_api_syncer,
                    oddspapi_syncer=oddspapi_syncer,
                    trace_id=trace_id,
                    recovery_budget=recovery_budget,
                )
            except Exception as exc:
                session.rollback()
                if selected_provider == MatchOddsSyncProvider.ODDSPAPI:
                    for match_id in the_odds_api_ids:
                        _record_fallback_error(fallback_errors, match_id, str(exc))
                else:
                    batch_errors.append(str(exc))
            requests_used += int(getattr(result, "requests_used", 0) or 0)
            credits_used += int(getattr(result, "credits_used", 0) or 0)
            retry_count += int(getattr(result, "retry_count", 0) or 0)
            retry_success_count += int(getattr(result, "retry_success_count", 0) or 0)
            raw_provider_requests_used = getattr(result, "provider_requests_used", None)
            if raw_provider_requests_used is not None:
                used_value = int(raw_provider_requests_used or 0)
                provider_requests_used = (
                    used_value
                    if provider_requests_used is None
                    else max(provider_requests_used, used_value)
                )
            raw_provider_requests_remaining = getattr(result, "provider_requests_remaining", None)
            if raw_provider_requests_remaining is not None:
                remaining_value = int(raw_provider_requests_remaining)
                provider_requests_remaining = (
                    remaining_value
                    if provider_requests_remaining is None
                    else min(provider_requests_remaining, remaining_value)
                )
            result_rate_limit_wait_seconds = max(result_rate_limit_wait_seconds, float(getattr(result, "rate_limit_wait_seconds", 0.0) or 0.0))
            result_recovery_elapsed_seconds = max(result_recovery_elapsed_seconds, float(getattr(result, "recovery_elapsed_seconds", 0.0) or 0.0))
            result_recovery_budget_remaining_seconds = min(result_recovery_budget_remaining_seconds, float(getattr(result, "recovery_budget_remaining_seconds", recovery_budget.limit_seconds)))
            if result is not None:
                _merge_the_odds_api_primary_results(
                    result=result,
                    season_match_ids=the_odds_api_ids,
                    primary_results=primary_results,
                    not_attempted_ids=not_attempted_ids,
                )
                new_snapshot_match_ids = _new_the_odds_api_snapshot_match_ids(
                    session=session,
                    match_ids=the_odds_api_ids,
                    snapshot_ids_before=the_odds_api_snapshot_ids_before,
                )
                _merge_the_odds_api_source_match_results(
                    session=session,
                    match_ids=the_odds_api_ids,
                    source_match_states_before=source_match_states_before,
                    new_snapshot_match_ids=new_snapshot_match_ids,
                    primary_results=primary_results,
                )
                _merge_new_the_odds_api_snapshot_results(
                    new_snapshot_match_ids=new_snapshot_match_ids,
                    primary_results=primary_results,
                )
                _log_standard_timepoint_coverage(session, the_odds_api_ids, stage="the_odds_api_after")
            unresolved_ids = _unresolved_match_ids(session, unresolved_ids)

        if unresolved_ids:
            fallback_invoked_ids.update(unresolved_ids)
            fallback_attempted_ids.update(unresolved_ids)
            _log_standard_timepoint_coverage(session, unresolved_ids, stage="zqcf918_before")
            try:
                zqcf918_result = zqcf918_syncer(
                    session=session,
                    match_ids=unresolved_ids,
                )
                requests_used += int(zqcf918_result.get("requests", 0) or 0)
                credits_used += int(zqcf918_result.get("credits", 0) or 0)
                for item in zqcf918_result.get("failed", []):
                    _record_fallback_error(
                        fallback_errors,
                        int(item["match_id"]),
                        str(item.get("message") or "zqcf918 failed"),
                    )
                for item in zqcf918_result.get("skipped", []):
                    _record_fallback_error(
                        fallback_errors,
                        int(item["match_id"]),
                        str(item.get("message") or "zqcf918 skipped"),
                    )
                _log_standard_timepoint_coverage(session, unresolved_ids, stage="zqcf918_after")
            except Exception as exc:
                session.rollback()
                for match_id in unresolved_ids:
                    _record_fallback_error(fallback_errors, match_id, str(exc))

    success: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    final_not_attempted: list[dict[str, Any]] = []
    for match_id in sorted(eligible_match_ids):
        primary_result = primary_results.get(match_id)
        trusted_source = _trusted_snapshot_source(session, match_id)
        if trusted_source is not None:
            primary_refresh_status = _successful_primary_refresh_status(
                primary_result=primary_result,
                had_trusted_odds=trusted_sources_before[match_id] is not None,
                fallback_was_invoked=match_id in fallback_invoked_ids,
            )
            attempt_count = primary_result.attempt_count if primary_result is not None else 1
            success.append(
                {
                    "match_id": match_id,
                    "message": "赔率已刷新",
                    "source": trusted_source,
                    "attempt_count": attempt_count,
                    "retried": attempt_count > 1,
                    "primary_refresh_status": primary_refresh_status,
                    "primary_refresh_error": _primary_error(primary_result),
                }
            )
            continue

        failure_item = _final_failure_item(
            match_id=match_id,
            provider=selected_provider,
            primary_result=primary_result,
            fallback_error=fallback_errors.get(match_id),
            fallback_was_invoked=match_id in fallback_invoked_ids,
        )
        if (
            match_id in not_attempted_ids
            and match_id not in fallback_attempted_ids
            and (primary_result is None or primary_result.status == "not_attempted")
        ):
            final_not_attempted.append(failure_item)
        else:
            failed.append(failure_item)

    return _finalize_sync_result(
        trace_id=trace_id,
        recovery_budget=recovery_budget,
        success=success,
        failed=failed,
        skipped=skipped,
        not_attempted=final_not_attempted,
        requests=requests_used,
        credits=credits_used,
        retry_count=retry_count,
        retry_success_count=retry_success_count,
        provider_requests_used=provider_requests_used,
        provider_requests_remaining=provider_requests_remaining,
        result_rate_limit_wait_seconds=result_rate_limit_wait_seconds,
        result_recovery_elapsed_seconds=result_recovery_elapsed_seconds,
        result_recovery_budget_remaining_seconds=result_recovery_budget_remaining_seconds,
        error_message="; ".join(dict.fromkeys(batch_errors)) or None,
    )


def _merge_the_odds_api_primary_results(
    *,
    result: Any,
    season_match_ids: set[int],
    primary_results: dict[int, TheOddsApiMatchSyncResult],
    not_attempted_ids: set[int],
) -> None:
    for match_result in tuple(getattr(result, "match_results", ()) or ()):
        if match_result.match_id not in season_match_ids:
            continue
        primary_results[match_result.match_id] = match_result
        if match_result.status == "not_attempted":
            not_attempted_ids.add(match_result.match_id)

    explicit_not_attempted_ids = (
        set(getattr(result, "not_attempted_match_ids", ()) or ()) & season_match_ids
    )
    not_attempted_ids.update(explicit_not_attempted_ids)
    batch_error = getattr(result, "error_message", None)
    for match_id in explicit_not_attempted_ids:
        if match_id in primary_results:
            continue
        primary_results[match_id] = TheOddsApiMatchSyncResult(
            match_id=match_id,
            status="not_attempted",
            error_message=str(batch_error or "The Odds API request not attempted"),
            error_code=_error_code_from_value(batch_error) or "not_attempted",
        )


def _merge_the_odds_api_source_match_results(
    *,
    session: Session,
    match_ids: set[int],
    source_match_states_before: dict[int, tuple[Any, ...]],
    new_snapshot_match_ids: set[int],
    primary_results: dict[int, TheOddsApiMatchSyncResult],
) -> None:
    rows = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.match_id.in_(match_ids))
        .filter(OddsSourceMatch.source_name == THE_ODDS_API_SOURCE_NAME)
        .all()
    )
    for row in rows:
        if (
            row.match_id in primary_results
            or not row.historical_odds_status
            or source_match_states_before.get(row.match_id) == _source_match_odds_state(row)
        ):
            continue
        status = row.historical_odds_status
        normalized_status = status if status in {"success", "partial_success"} else "failed"
        if normalized_status == "failed" and row.match_id in new_snapshot_match_ids:
            normalized_status = "partial_success"
        primary_results[row.match_id] = TheOddsApiMatchSyncResult(
            match_id=row.match_id,
            status=normalized_status,
            error_message=_format_the_odds_api_primary_error(
                status,
                row.historical_odds_error,
            ),
            error_code=(
                None
                if normalized_status == "success"
                else _error_code_from_value(row.historical_odds_error) or status
            ),
        )


def _merge_new_the_odds_api_snapshot_results(
    *,
    new_snapshot_match_ids: set[int],
    primary_results: dict[int, TheOddsApiMatchSyncResult],
) -> None:
    for match_id in new_snapshot_match_ids:
        if match_id in primary_results:
            continue
        primary_results[match_id] = TheOddsApiMatchSyncResult(
            match_id=match_id,
            status="success",
        )


def _new_the_odds_api_snapshot_match_ids(
    *,
    session: Session,
    match_ids: set[int],
    snapshot_ids_before: set[int],
) -> set[int]:
    rows = (
        session.query(HistoricalOddsSnapshot.id, HistoricalOddsSnapshot.match_id)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .all()
    )
    return {
        match_id
        for snapshot_id, match_id in rows
        if snapshot_id not in snapshot_ids_before
    }


def _the_odds_api_snapshot_ids(session: Session, match_ids: set[int]) -> set[int]:
    if not match_ids:
        return set()
    return {
        snapshot_id
        for (snapshot_id,) in (
            session.query(HistoricalOddsSnapshot.id)
            .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
            .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
            .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
            .all()
        )
    }


def _the_odds_api_source_match_states(
    session: Session,
    match_ids: set[int],
) -> dict[int, tuple[Any, ...]]:
    if not match_ids:
        return {}
    rows = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.match_id.in_(match_ids))
        .filter(OddsSourceMatch.source_name == THE_ODDS_API_SOURCE_NAME)
        .all()
    )
    return {row.match_id: _source_match_odds_state(row) for row in rows}


def _source_match_odds_state(row: OddsSourceMatch) -> tuple[Any, ...]:
    return (
        row.historical_odds_status,
        row.historical_odds_checked_at,
        row.historical_odds_error,
    )


def _successful_primary_refresh_status(
    *,
    primary_result: TheOddsApiMatchSyncResult | None,
    had_trusted_odds: bool,
    fallback_was_invoked: bool,
) -> str:
    if primary_result is not None:
        if primary_result.status in {"success", "partial_success"}:
            return primary_result.status
        if primary_result.status == "failed":
            return "failed_existing_odds_used" if had_trusted_odds else "failed_fallback_used"
        if primary_result.status == "not_attempted":
            return (
                "not_attempted_existing_odds_used"
                if had_trusted_odds
                else "not_attempted_fallback_used"
            )
    if fallback_was_invoked and not had_trusted_odds:
        return "unreported_fallback_used"
    if had_trusted_odds:
        return "unreported_existing_odds_used"
    return "success"


def _primary_error(primary_result: TheOddsApiMatchSyncResult | None) -> str | None:
    if primary_result is None:
        return None
    return primary_result.error_code or primary_result.error_message


def _final_failure_item(
    *,
    match_id: int,
    provider: MatchOddsSyncProvider,
    primary_result: TheOddsApiMatchSyncResult | None,
    fallback_error: str | None,
    fallback_was_invoked: bool,
) -> dict[str, Any]:
    primary_message = primary_result.error_message if primary_result is not None else None
    message = primary_message or "未获取到可用赔率"
    if fallback_error:
        message = f"{message}; fallback: {fallback_error}" if primary_message else fallback_error
    attempt_count = primary_result.attempt_count if primary_result is not None else 1
    primary_status = primary_result.status if primary_result is not None else "unknown"
    error_code = primary_result.error_code if primary_result is not None else None
    if not error_code:
        error_code = "fallback_failed" if fallback_error else "odds_unavailable"
    return {
        "match_id": match_id,
        "message": message,
        "source": provider.value,
        "error_code": error_code,
        "failure_stage": "fallback" if fallback_was_invoked else "primary",
        "attempt_count": attempt_count,
        "retry_exhausted": (
            primary_result.retry_exhausted if primary_result is not None else False
        ),
        "fallback_error": fallback_error,
        "primary_refresh_status": primary_status,
        "primary_refresh_error": _primary_error(primary_result),
    }


def _finalize_sync_result(
    *,
    trace_id: str,
    recovery_budget: TheOddsApiRecoveryBudget,
    success: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    not_attempted: list[dict[str, Any]],
    requests: int = 0,
    credits: int = 0,
    retry_count: int = 0,
    retry_success_count: int = 0,
    provider_requests_used: int | None = None,
    provider_requests_remaining: int | None = None,
    result_rate_limit_wait_seconds: float = 0.0,
    result_recovery_elapsed_seconds: float = 0.0,
    result_recovery_budget_remaining_seconds: float = 120.0,
    error_message: str | None = None,
) -> SyncResultPayload:
    success.sort(key=lambda item: item["match_id"])
    failed.sort(key=lambda item: item["match_id"])
    skipped.sort(key=lambda item: item["match_id"])
    not_attempted.sort(key=lambda item: item["match_id"])
    unresolved_count = len(failed) + len(not_attempted)
    if not unresolved_count:
        odds_status = "success"
    else:
        odds_status = "partial" if success else "failed"
    retry_recovered_match_count = sum(
        bool(item.get("retried"))
        and item.get("primary_refresh_status") in {"success", "partial_success"}
        for item in success
    )

    for status, items in (
        ("success", success),
        ("failed", failed),
        ("skipped", skipped),
        ("not_attempted", not_attempted),
    ):
        for item in items:
            logger.info(
                "match_odds_sync_result trace_id=%s match_id=%s status=%s "
                "primary_refresh_status=%s failure_stage=%s",
                trace_id,
                item["match_id"],
                status,
                item.get("primary_refresh_status") or "-",
                item.get("failure_stage") or "-",
            )

    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "not_attempted": not_attempted,
        "odds_status": odds_status,
        "trace_id": trace_id,
        "error_message": error_message,
        "requests": requests,
        "credits": credits,
        "provider_requests_used": provider_requests_used,
        "provider_requests_remaining": provider_requests_remaining,
        "retry_count": retry_count,
        "retry_success_count": retry_success_count,
        "retry_recovered_match_count": retry_recovered_match_count,
        "rate_limit_wait_seconds": max(
            recovery_budget.limiter_wait_seconds,
            result_rate_limit_wait_seconds,
        ),
        "recovery_elapsed_seconds": max(
            recovery_budget.consumed_seconds,
            result_recovery_elapsed_seconds,
        ),
        "recovery_budget_remaining_seconds": min(
            recovery_budget.remaining_seconds,
            result_recovery_budget_remaining_seconds,
        ),
    }


def has_trusted_historical_odds(session: Session, match_id: int) -> bool:
    return _trusted_snapshot_source(session, match_id) is not None


def _trusted_snapshot_source(session: Session, match_id: int) -> str | None:
    for source_name, bookmaker in TRUSTED_SNAPSHOT_PRIORITY:
        if (
            session.query(HistoricalOddsSnapshot.id)
            .filter(HistoricalOddsSnapshot.match_id == match_id)
            .filter(HistoricalOddsSnapshot.source_name == source_name)
            .filter(HistoricalOddsSnapshot.bookmaker == bookmaker)
            .first()
            is not None
        ):
            return source_name
    return None


def _format_the_odds_api_primary_error(status: str | None, error: str | None) -> str | None:
    if not status and not error:
        return None
    label = "The Odds API"
    if status:
        label = f"{label} {status}"
    if error:
        return f"{label}: {error}"
    return label


def _error_code_from_value(value: Any) -> str | None:
    if value is None:
        return None
    explicit_error_code = getattr(value, "error_code", None)
    if explicit_error_code:
        return str(explicit_error_code)
    normalized = str(value).lower()
    for error_code in (
        "extra_time_budget_exhausted",
        "request_budget_exhausted",
        "read_timeout",
        "connect_timeout",
        "rate_limit",
    ):
        if error_code in normalized:
            return error_code
    return None


def _record_fallback_error(errors: dict[int, str], match_id: int, message: str) -> None:
    if match_id in errors:
        errors[match_id] = f"{errors[match_id]}; {message}"
    else:
        errors[match_id] = message


def has_priority_pinnacle_historical_odds(session: Session, match_id: int) -> bool:
    return has_trusted_historical_odds(session, match_id)


def run_default_the_odds_api_sync_for_session(**kwargs: Any) -> Any:
    trace_id = kwargs.get("trace_id") or uuid4().hex[:12]
    recovery_budget = kwargs.get("recovery_budget")
    if recovery_budget is None:
        recovery_budget = TheOddsApiRecoveryBudget(limit_seconds=120.0)
    kwargs["trace_id"] = trace_id
    kwargs["recovery_budget"] = recovery_budget
    settings = load_project_settings()
    raw_client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=40,
        request_budget=max(50, int(kwargs.get("max_matches", 1) or 1) * 20),
        recovery_budget=recovery_budget,
        trace_id=trace_id,
    )
    client = TheOddsApiSyncClient(raw_client)
    return run_the_odds_api_sync_for_session(client=client, **kwargs)


def _run_provider_sync(
    *,
    provider: MatchOddsSyncProvider,
    session: Session,
    season: int,
    match_ids: set[int],
    the_odds_api_syncer: Callable[..., Any],
    oddspapi_syncer: Callable[..., Any],
    trace_id: str,
    recovery_budget: TheOddsApiRecoveryBudget,
) -> Any:
    if provider == MatchOddsSyncProvider.THE_ODDS_API:
        return the_odds_api_syncer(
            session=session,
            season=season,
            max_matches=len(match_ids),
            match_ids=match_ids,
            refresh_existing=True,
            trace_id=trace_id,
            recovery_budget=recovery_budget,
        )
    return oddspapi_syncer(
        season=season,
        max_matches=len(match_ids),
        request_budget=max(50, len(match_ids) * 20),
        timeout_seconds=40,
        max_snapshots_per_match=151,
        match_ids=match_ids,
        historical_odds_cooldown_seconds=6.0,
        refresh_pre_kickoff_existing=True,
    )


def _zqcf918_fallback_match_ids(
    session: Session,
    matches: list[Match],
    season_match_ids: set[int],
) -> set[int]:
    return {
        match.id
        for match in matches
        if match.id in season_match_ids and not has_trusted_historical_odds(session, match.id)
    }


def _unresolved_match_ids(session: Session, match_ids: set[int]) -> set[int]:
    return {
        match_id for match_id in match_ids
        if not has_complete_core_execution_timepoint_coverage(session, match_id)
    }


def _log_standard_timepoint_coverage(
    session: Session,
    match_ids: set[int],
    *,
    stage: str,
) -> None:
    for match_id in sorted(match_ids):
        coverage = get_standard_execution_timepoint_coverage(session, match_id)
        if coverage is None:
            logger.info(
                "standard_timepoint_coverage stage=%s match_id=%s core=0/12 full=0/18 missing=match_not_found",
                stage,
                match_id,
            )
            continue
        missing_full = ",".join(
            f"{market_type}:T-{target}"
            for market_type, target in coverage.missing_cells
        ) or "-"
        missing_core = ",".join(
            f"{market_type}:T-{target}"
            for market_type, target in coverage.core_missing_cells
        ) or "-"
        logger.info(
            "standard_timepoint_coverage stage=%s match_id=%s core=%s/%s full=%s/%s missing_core=%s missing_full=%s",
            stage,
            match_id,
            coverage.core_available_count,
            coverage.core_total_count,
            coverage.available_count,
            coverage.total_count,
            missing_core,
            missing_full,
        )


def _merge_oddspapi_primary_results(
    *,
    session: Session,
    match_ids: set[int],
    result: Any,
    primary_results: dict[int, TheOddsApiMatchSyncResult],
) -> None:
    error_message = getattr(result, "error_message", None)
    for match_id in match_ids:
        if has_trusted_historical_odds(session, match_id):
            primary_results[match_id] = TheOddsApiMatchSyncResult(
                match_id=match_id,
                status="success",
            )
        elif error_message:
            primary_results[match_id] = TheOddsApiMatchSyncResult(
                match_id=match_id,
                status="failed",
                error_message=str(error_message),
                error_code=_error_code_from_value(error_message),
            )

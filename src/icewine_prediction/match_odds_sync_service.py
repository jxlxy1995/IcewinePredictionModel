from enum import StrEnum
from typing import Any, Callable

from sqlalchemy.orm import Session

from icewine_prediction.models import HistoricalOddsSnapshot, Match
from icewine_prediction.oddspapi_sync_runner import run_oddspapi_sync_result
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    PINNACLE_SOURCE_PRIORITY,
    THE_ODDS_API_SOURCE_NAME,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.the_odds_api_client import TheOddsApiClient
from icewine_prediction.the_odds_api_sync_runner import run_the_odds_api_sync_for_session
from icewine_prediction.the_odds_api_sync_runner import TheOddsApiSyncClient


class MatchOddsSyncProvider(StrEnum):
    THE_ODDS_API = THE_ODDS_API_SOURCE_NAME
    ODDSPAPI = "oddspapi"


SyncResultPayload = dict[str, list[dict[str, Any]] | int]


def run_match_odds_sync_for_session(
    *,
    session: Session,
    match_ids: list[int],
    provider: MatchOddsSyncProvider | str = MatchOddsSyncProvider.THE_ODDS_API,
    the_odds_api_syncer: Callable[..., Any] | None = None,
    oddspapi_syncer: Callable[..., Any] = run_oddspapi_sync_result,
) -> SyncResultPayload:
    if not match_ids:
        return {"success": [], "failed": [], "skipped": [], "requests": 0}

    matches = session.query(Match).filter(Match.id.in_(match_ids)).all()
    matches_by_id = {match.id: match for match in matches}
    skipped = [
        {"match_id": match_id, "message": "缺少比赛"}
        for match_id in match_ids
        if match_id not in matches_by_id
    ]
    seasons = sorted({match.season for match in matches if match.season is not None})
    skipped.extend(
        {"match_id": match.id, "message": "缺少赛季"}
        for match in matches
        if match.season is None
    )
    if not seasons:
        return {"success": [], "failed": [], "skipped": skipped, "requests": 0}

    selected_provider = MatchOddsSyncProvider(provider)
    the_odds_api_syncer = the_odds_api_syncer or run_default_the_odds_api_sync_for_session
    requests_used = 0
    run_errors: dict[int, str] = {}
    for season in seasons:
        season_match_ids = {
            match.id
            for match in matches
            if match.season == season
        }
        if not season_match_ids:
            continue
        try:
            result = _run_provider_sync(
                provider=selected_provider,
                session=session,
                season=season,
                match_ids=season_match_ids,
                the_odds_api_syncer=the_odds_api_syncer,
                oddspapi_syncer=oddspapi_syncer,
            )
            requests_used += int(getattr(result, "requests_used", 0) or 0)
            error_message = getattr(result, "error_message", None)
            if error_message:
                for match_id in season_match_ids:
                    run_errors[match_id] = str(error_message)
        except Exception as exc:
            for match_id in season_match_ids:
                run_errors[match_id] = str(exc)

    success_ids = []
    failed_ids = []
    for match in matches:
        if match.season is None:
            continue
        if has_priority_pinnacle_historical_odds(session, match.id):
            success_ids.append(match.id)
        else:
            failed_ids.append(match.id)

    return {
        "success": [
            {"match_id": match_id, "message": "赔率已刷新"}
            for match_id in sorted(success_ids)
        ],
        "failed": [
            {
                "match_id": match_id,
                "message": run_errors.get(match_id) or "未获取到可用赔率",
            }
            for match_id in sorted(set(failed_ids) - set(success_ids))
        ],
        "skipped": skipped,
        "requests": requests_used,
    }


def has_priority_pinnacle_historical_odds(session: Session, match_id: int) -> bool:
    return (
        session.query(HistoricalOddsSnapshot.id)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .filter(HistoricalOddsSnapshot.source_name.in_(PINNACLE_SOURCE_PRIORITY))
        .first()
        is not None
    )


def run_default_the_odds_api_sync_for_session(**kwargs: Any) -> Any:
    settings = load_project_settings()
    raw_client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=40,
        request_budget=max(50, int(kwargs.get("max_matches", 1) or 1) * 20),
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
) -> Any:
    if provider == MatchOddsSyncProvider.THE_ODDS_API:
        return the_odds_api_syncer(
            session=session,
            season=season,
            max_matches=len(match_ids),
            match_ids=match_ids,
            refresh_existing=True,
        )
    return oddspapi_syncer(
        season=season,
        max_matches=len(match_ids),
        request_budget=max(50, len(match_ids) * 20),
        timeout_seconds=40,
        max_snapshots_per_match=151,
        match_ids=match_ids,
        historical_odds_cooldown_seconds=7.5,
        refresh_pre_kickoff_existing=True,
    )

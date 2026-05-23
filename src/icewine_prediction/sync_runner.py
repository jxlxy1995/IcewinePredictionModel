from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.models import Match
from icewine_prediction.settings import ProjectSettings, load_project_settings
from icewine_prediction.sources.api_football_client import ApiFootballApiError, ApiFootballClient
from icewine_prediction.sources.api_football_provider import ApiFootballProvider
from icewine_prediction.sync_service import (
    FixtureSyncResult,
    OddsSyncResult,
    upsert_fixtures,
    upsert_odds_snapshots,
)
from icewine_prediction.time_utils import now_beijing


def build_sync_summary(
    operation: str,
    created: int,
    updated: int,
    skipped: int,
    requests_used: int,
) -> str:
    return (
        f"{operation}: created={created}, updated={updated}, "
        f"skipped={skipped}, requests={requests_used}"
    )


@dataclass(frozen=True)
class OddsFetchStoreResult:
    created_odds_snapshots: int = 0
    skipped_odds_snapshots: int = 0
    failed_fixture_id: str | None = None
    error_message: str | None = None


def build_api_football_provider(settings: ProjectSettings) -> ApiFootballProvider:
    source = settings.sources["api_football"]
    client = ApiFootballClient(
        base_url=source.base_url,
        api_key=settings.api_football_key,
        timeout_seconds=source.timeout_seconds,
        daily_request_budget=source.daily_request_budget,
    )
    return ApiFootballProvider(client)


def _open_session():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def select_upcoming_fixture_ids_for_odds(
    session: Session,
    days: int,
    start_time: datetime | None = None,
) -> list[str]:
    start = start_time or now_beijing()
    end = start + timedelta(days=days)
    fixture_ids = (
        session.query(Match.source_match_id)
        .filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= start)
        .filter(Match.kickoff_time <= end)
        .filter(Match.source_match_id.isnot(None))
        .order_by(Match.kickoff_time.asc())
        .all()
    )
    return [fixture_id for (fixture_id,) in fixture_ids if fixture_id is not None]


def select_recent_finished_fixture_ids_for_odds(
    session: Session,
    days: int,
    end_time: datetime | None = None,
) -> list[str]:
    end = end_time or now_beijing()
    start = end - timedelta(days=days)
    fixture_ids = (
        session.query(Match.source_match_id)
        .filter(Match.status == "finished")
        .filter(Match.kickoff_time >= start)
        .filter(Match.kickoff_time <= end)
        .filter(Match.source_match_id.isnot(None))
        .order_by(Match.kickoff_time.desc())
        .all()
    )
    return [fixture_id for (fixture_id,) in fixture_ids if fixture_id is not None]


def fetch_and_store_odds_snapshots(
    session: Session,
    provider: ApiFootballProvider,
    fixture_ids: list[str],
) -> OddsFetchStoreResult:
    created = 0
    skipped = 0
    for fixture_id in fixture_ids:
        try:
            snapshots = provider.fetch_odds_for_fixtures([fixture_id])
        except ApiFootballApiError as exc:
            return OddsFetchStoreResult(
                created_odds_snapshots=created,
                skipped_odds_snapshots=skipped,
                failed_fixture_id=fixture_id,
                error_message=str(exc),
            )
        result: OddsSyncResult = upsert_odds_snapshots(session, snapshots)
        created += result.created_odds_snapshots
        skipped += result.skipped_odds_snapshots
    return OddsFetchStoreResult(
        created_odds_snapshots=created,
        skipped_odds_snapshots=skipped,
    )


def fetch_and_store_historical_fixtures(
    session: Session,
    provider: ApiFootballProvider,
    league_id: int,
    season: int,
) -> FixtureSyncResult:
    fixtures = provider.fetch_historical_fixtures(league_id=league_id, season=season)
    return upsert_fixtures(session, fixtures)


def run_sync_upcoming(days: int) -> str:
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    fixtures = provider.fetch_upcoming_fixtures(settings.leagues, days=days)
    with _open_session() as session:
        result = upsert_fixtures(session, fixtures)
    return build_sync_summary(
        operation="upcoming",
        created=result.created_matches,
        updated=result.updated_matches,
        skipped=0,
        requests_used=provider.client.request_count,
    )


def run_sync_odds(days: int) -> str:
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    with _open_session() as session:
        fixture_ids = select_upcoming_fixture_ids_for_odds(session, days=days)
        result = fetch_and_store_odds_snapshots(session, provider, fixture_ids)
    summary = build_sync_summary(
        operation=f"odds:{days}",
        created=result.created_odds_snapshots,
        updated=0,
        skipped=result.skipped_odds_snapshots,
        requests_used=provider.client.request_count,
    )
    if result.failed_fixture_id is not None:
        return f"{summary}, failed_fixture={result.failed_fixture_id}, error={result.error_message}"
    return summary


def run_sync_historical_odds(days: int) -> str:
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    with _open_session() as session:
        fixture_ids = select_recent_finished_fixture_ids_for_odds(session, days=days)
        result = fetch_and_store_odds_snapshots(session, provider, fixture_ids)
    summary = build_sync_summary(
        operation=f"historical-odds:{days}",
        created=result.created_odds_snapshots,
        updated=0,
        skipped=result.skipped_odds_snapshots,
        requests_used=provider.client.request_count,
    )
    if result.failed_fixture_id is not None:
        return f"{summary}, failed_fixture={result.failed_fixture_id}, error={result.error_message}"
    return summary


def run_sync_results(from_date: date, to_date: date) -> str:
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    fixtures = provider.fetch_results(settings.leagues, from_date=from_date, to_date=to_date)
    with _open_session() as session:
        result = upsert_fixtures(session, fixtures)
    return build_sync_summary(
        operation="results",
        created=result.created_matches,
        updated=result.updated_matches,
        skipped=0,
        requests_used=provider.client.request_count,
    )


def run_sync_history(league_id: int, season: int) -> str:
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    with _open_session() as session:
        result = fetch_and_store_historical_fixtures(
            session,
            provider,
            league_id=league_id,
            season=season,
        )
    return build_sync_summary(
        operation=f"history:{league_id}:{season}",
        created=result.created_matches,
        updated=result.updated_matches,
        skipped=0,
        requests_used=provider.client.request_count,
    )

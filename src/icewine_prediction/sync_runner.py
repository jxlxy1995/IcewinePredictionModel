from datetime import date

from sqlalchemy import text

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.settings import ProjectSettings, load_project_settings
from icewine_prediction.sources.api_football_client import ApiFootballClient
from icewine_prediction.sources.api_football_provider import ApiFootballProvider
from icewine_prediction.sync_service import upsert_fixtures, upsert_odds_snapshots


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
        fixture_ids = [
            source_match_id
            for source_match_id in session.execute(text("select source_match_id from matches")).scalars().all()
            if source_match_id is not None
        ]
        snapshots = provider.fetch_odds_for_fixtures(fixture_ids)
        result = upsert_odds_snapshots(session, snapshots)
    return build_sync_summary(
        operation=f"odds:{days}",
        created=result.created_odds_snapshots,
        updated=0,
        skipped=result.skipped_odds_snapshots,
        requests_used=provider.client.request_count,
    )


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

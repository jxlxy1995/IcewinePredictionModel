from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    build_baseline_training_dataset_market_baseline_report,
    write_baseline_training_dataset_market_baseline_report,
)
from icewine_prediction.baseline_training_dataset_qa_service import (
    build_baseline_training_dataset_qa_report,
    write_baseline_training_dataset_qa_report,
)
from icewine_prediction.baseline_training_dataset_service import (
    build_baseline_training_dataset,
    write_baseline_training_dataset_csv,
    write_baseline_training_dataset_report,
)
from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.display_service import (
    DisplayNameService,
    load_display_names,
    save_team_display_names,
)
from icewine_prediction.display_translation_status_service import DisplayTranslationStatusService
from icewine_prediction.models import (
    DataSyncRun,
    DataSyncRunItem,
    HistoricalOddsSnapshot,
    League,
    Match,
    OddsSourceMatch,
    OddsSnapshot,
    RecommendationRecord,
    Team,
    TrainingRun,
)
from icewine_prediction.oddspapi_backfill_audit_service import (
    OddsPapiBackfillAuditReport,
    build_oddspapi_backfill_audit_for_session,
)
from icewine_prediction.oddspapi_worker_process_service import _is_process_running
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueScore,
    PaperQueueScoreResult,
    build_paper_recommendation_queue,
)
from icewine_prediction.paper_confidence_service import build_paper_confidence_workspace
from icewine_prediction.match_list_workspace_service import (
    build_match_detail,
    build_match_list_workspace,
    record_sync_run,
    select_match_list_sync_targets,
)
from icewine_prediction.paper_recommendation_tracking_service import (
    backfill_paper_record_from_candidate,
    build_paper_tracking_workspace,
    create_paper_record_from_queue_row,
    edit_paper_record,
    settle_paper_records,
    void_paper_record,
)
from icewine_prediction.oddspapi_sync_runner import run_oddspapi_sync_result
from icewine_prediction.sources.api_football_client import ApiFootballApiError
from icewine_prediction.sources.api_football_mapper import map_fixtures
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sync_runner import build_api_football_provider
from icewine_prediction.sync_service import league_internal_name, upsert_fixtures, upsert_odds_snapshots
from icewine_prediction.time_utils import now_beijing
from icewine_prediction.training_orchestration_service import (
    TrainingRunAlreadyRunning,
    build_training_snapshot_paths,
    create_training_run,
    get_latest_training_run,
    run_training_full_refresh,
)


def create_web_app(
    *,
    session_factory: Callable[[], Session] | None = None,
    log_dir: str | Path = "logs/odds",
    process_running_checker: Callable[[int], bool] = _is_process_running,
    display_name_service: DisplayNameService | None = None,
    display_translation_status_service: DisplayTranslationStatusService | None = None,
    display_names_path: Path = Path("config/display_names.yaml"),
    baseline_dataset_path: Path = Path("local_data/training/baseline_main_leagues_20260529.csv"),
    baseline_dataset_report_path: Path = Path(
        "docs/数据审计/20260529-baseline-training-dataset.md"
    ),
    baseline_qa_report_path: Path = Path(
        "docs/数据审计/20260529-baseline-training-dataset-qa.md"
    ),
    baseline_market_report_path: Path = Path(
        "docs/模型实验/20260529-close-market-baseline-evaluation.md"
    ),
    paper_queue_scorer: Callable[[dict[str, str]], PaperQueueScoreResult] | None = None,
    match_list_fixtures_results_syncer: Callable[[list[int]], dict[str, Any] | str] | None = None,
    match_list_fixture_range_syncer: Callable[[datetime, datetime, str | None], dict[str, Any] | str] | None = None,
    match_list_odds_syncer: Callable[[list[int]], dict[str, Any] | str] | None = None,
    training_full_refresh_runner: Callable[[int], None] | None = None,
    clock: Callable[[], datetime] = now_beijing,
) -> FastAPI:
    if session_factory is None:
        engine = create_database_engine()
        initialize_database(engine)
        session_factory = create_session_factory(engine)
    log_dir = Path(log_dir)
    display_name_service = display_name_service or DisplayNameService(load_display_names(display_names_path))
    display_translation_status_service = (
        display_translation_status_service or DisplayTranslationStatusService()
    )

    app = FastAPI(title="Icewine Prediction Console API")
    response_cache = WebResponseCache(ttl_seconds=60.0)
    match_list_fixtures_results_syncer = (
        match_list_fixtures_results_syncer or _run_match_list_fixtures_results_sync
    )
    match_list_fixture_range_syncer = (
        match_list_fixture_range_syncer or _run_match_list_fixture_range_sync
    )
    match_list_odds_syncer = match_list_odds_syncer or _run_match_list_odds_sync
    if training_full_refresh_runner is None:
        training_full_refresh_runner = lambda run_id: _start_training_full_refresh_thread(
            session_factory,
            run_id,
            display_name_service=display_name_service,
            clock=clock,
        )

    def cached_response(cache_key: tuple[Any, ...], builder: Callable[[], Any]) -> Any:
        return response_cache.get_or_set(cache_key, builder)

    def clear_cache_prefix(*prefixes: str) -> None:
        response_cache.clear_prefixes(*prefixes)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dashboard/summary")
    def dashboard_summary() -> dict[str, int]:
        return cached_response(
            ("dashboard-summary",),
            lambda: _with_session(session_factory, build_dashboard_summary),
        )

    @app.get("/api/display/translation-status")
    def display_translation_status() -> dict[str, Any]:
        return {
            "done_league_seasons": sorted(
                display_translation_status_service.list_done_keys()
            )
        }

    @app.get("/api/leagues/coverage")
    def league_coverage() -> list[dict[str, Any]]:
        return cached_response(
            ("league-coverage",),
            lambda: _with_session(
                session_factory,
                lambda session: build_league_coverage(
                    session,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.get("/api/workers")
    def workers() -> list[dict[str, Any]]:
        return build_worker_statuses(log_dir, process_running_checker=process_running_checker)

    @app.get("/api/oddspapi/backfill-audit")
    def oddspapi_backfill_audit(season: int = 2025, top_errors: int = 5) -> dict[str, Any]:
        return cached_response(
            ("oddspapi-backfill-audit", season, top_errors),
            lambda: _with_session(
                session_factory,
                lambda session: build_oddspapi_backfill_audit_payload(
                    build_oddspapi_backfill_audit_for_session(
                        session=session,
                        season=season,
                        log_dir=log_dir,
                        top_errors=top_errors,
                        display_service=display_name_service,
                    )
                ),
            ),
        )

    @app.get("/api/unmatched")
    def unmatched() -> list[dict[str, Any]]:
        return cached_response(
            ("unmatched",),
            lambda: _with_session(
                session_factory,
                lambda session: build_unmatched_matches(
                    session,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.get("/api/display/missing-team-names")
    def missing_team_names() -> list[dict[str, Any]]:
        return cached_response(
            ("missing-team-names",),
            lambda: _with_session(
                session_factory,
                lambda session: build_missing_team_display_names(
                    session,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.get("/api/display/team-name-workspace")
    def team_name_workspace(league_id: int, season: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_team_display_name_workspace(
                session,
                league_id=league_id,
                season=season,
                display_name_service=display_name_service,
                display_translation_status_service=display_translation_status_service,
            )
            if payload is None:
                raise HTTPException(status_code=404, detail="联赛或赛季不存在")
            return payload

    @app.post("/api/display/team-name-workspace/done")
    def mark_team_name_workspace_done(payload: dict[str, int]) -> dict[str, Any]:
        league_id = int(payload["league_id"])
        season = int(payload["season"])
        display_translation_status_service.mark_done(league_id=league_id, season=season)
        return {
            "league_id": league_id,
            "season": season,
            "is_translation_done": True,
        }

    @app.post("/api/display/team-names")
    def save_display_team_names(payload: dict[str, dict[str, str]]) -> dict[str, int]:
        team_names = {
            team_name: display_name.strip()
            for team_name, display_name in payload.get("teams", {}).items()
            if display_name.strip()
        }
        save_team_display_names(team_names, path=display_names_path)
        display_name_service.display_names = load_display_names(display_names_path)
        clear_cache_prefix(
            "league-coverage",
            "missing-team-names",
            "matches-with-odds",
            "match-list-workspace",
            "paper-recommendation-workspace",
            "recommendation-records",
            "unmatched",
        )
        return {"saved_count": len(team_names)}

    @app.get("/api/matches/with-odds")
    def matches_with_odds() -> list[dict[str, Any]]:
        return cached_response(
            ("matches-with-odds",),
            lambda: _with_session(
                session_factory,
                lambda session: build_matches_with_odds(
                    session,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.get("/api/match-list/workspace")
    def match_list_workspace(
        start_time: str | None = None,
        end_time: str | None = None,
        league_name: str | None = None,
        status_filter: str = "all",
        odds_filter: str = "all",
        search: str | None = None,
    ) -> dict[str, Any]:
        return cached_response(
            ("match-list-workspace", start_time, end_time, league_name, status_filter, odds_filter, search),
            lambda: _with_session(
                session_factory,
                lambda session: build_match_list_workspace_payload(
                    build_match_list_workspace(
                        session,
                        now=clock(),
                        start_time=_parse_optional_datetime(start_time),
                        end_time=_parse_optional_datetime(end_time),
                        league_name=league_name,
                        status_filter=status_filter,
                        odds_filter=odds_filter,
                        search=search,
                        display_name_service=display_name_service,
                    )
                ),
            ),
        )

    @app.post("/api/match-list/sync/fixtures-results")
    def sync_match_list_fixtures_results(payload: dict[str, Any]) -> dict[str, Any]:
        started_at = clock()
        with session_factory() as session:
            matches = _select_sync_matches_from_payload(session, payload, now=clock())
            match_ids = [match.id for match in matches]
            try:
                report = _build_match_sync_report(
                    session=session,
                    sync_type="fixtures_results",
                    started_at=started_at,
                    finished_at=clock(),
                    matches=matches,
                    result=match_list_fixtures_results_syncer(match_ids),
                    display_name_service=display_name_service,
                )
                sync_result = _sync_run_counts_from_report(report)
                run = record_sync_run(
                    session,
                    sync_type="fixtures_results",
                    started_at=started_at,
                    finished_at=clock(),
                    status="success",
                    days=0,
                    **sync_result,
                )
                _persist_match_sync_run_items(session, run=run, report=report)
            except Exception as error:
                run = record_sync_run(
                    session,
                    sync_type="fixtures_results",
                    started_at=started_at,
                    finished_at=clock(),
                    status="failed",
                    days=0,
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    requests_used=0,
                    error_message=str(error),
                )
                raise HTTPException(status_code=500, detail=str(error)) from error
            clear_cache_prefix(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "missing-team-names",
                "paper-recommendation-workspace",
            )
            return {"sync_run": build_data_sync_run_payload(run), "report": report}

    @app.post("/api/match-list/sync/fixtures-range")
    def sync_match_list_fixture_range(payload: dict[str, Any]) -> dict[str, Any]:
        started_at = clock()
        start_time = _parse_optional_datetime(payload.get("start_time"))
        end_time = _parse_optional_datetime(payload.get("end_time"))
        if start_time is None or end_time is None:
            raise HTTPException(status_code=400, detail="fixtures range requires start_time and end_time")
        start_time = _as_beijing_datetime(start_time)
        end_time = _as_beijing_datetime(end_time)
        if end_time < start_time:
            raise HTTPException(status_code=400, detail="end_time must be greater than or equal to start_time")
        league_name = payload.get("league_name") or None
        with session_factory() as session:
            try:
                report = _build_fixture_range_sync_report(
                    sync_type="fixtures_range",
                    started_at=started_at,
                    finished_at=clock(),
                    result=match_list_fixture_range_syncer(start_time, end_time, league_name),
                )
                run = record_sync_run(
                    session,
                    sync_type="fixtures_range",
                    started_at=started_at,
                    finished_at=clock(),
                    status="success",
                    days=0,
                    created_count=int(report["created_count"]),
                    updated_count=int(report["updated_count"]),
                    skipped_count=int(report["skipped_count"]),
                    requests_used=int(report["requests_used"]),
                )
            except Exception as error:
                run = record_sync_run(
                    session,
                    sync_type="fixtures_range",
                    started_at=started_at,
                    finished_at=clock(),
                    status="failed",
                    days=0,
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    requests_used=0,
                    error_message=str(error),
                )
                raise HTTPException(status_code=500, detail=str(error)) from error
            clear_cache_prefix(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "missing-team-names",
                "paper-recommendation-workspace",
            )
            return {"sync_run": build_data_sync_run_payload(run), "report": report}

    @app.post("/api/match-list/sync/odds")
    def sync_match_list_odds(payload: dict[str, Any]) -> dict[str, Any]:
        started_at = clock()
        with session_factory() as session:
            matches = _select_sync_matches_from_payload(session, payload, now=clock())
            match_ids = [match.id for match in matches]
            try:
                report = _build_match_sync_report(
                    session=session,
                    sync_type="odds",
                    started_at=started_at,
                    finished_at=clock(),
                    matches=matches,
                    result=match_list_odds_syncer(match_ids),
                    display_name_service=display_name_service,
                )
                sync_result = _sync_run_counts_from_report(report)
                run = record_sync_run(
                    session,
                    sync_type="odds",
                    started_at=started_at,
                    finished_at=clock(),
                    status="success",
                    days=0,
                    **sync_result,
                )
                _persist_match_sync_run_items(session, run=run, report=report)
            except Exception as error:
                run = record_sync_run(
                    session,
                    sync_type="odds",
                    started_at=started_at,
                    finished_at=clock(),
                    status="failed",
                    days=0,
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    requests_used=0,
                    error_message=str(error),
                )
                raise HTTPException(status_code=500, detail=str(error)) from error
            clear_cache_prefix(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "oddspapi-backfill-audit",
                "paper-recommendation-workspace",
            )
            return {"sync_run": build_data_sync_run_payload(run), "report": report}

    @app.post("/api/matches/{match_id}/sync/fixtures-results")
    def sync_match_fixtures_results(match_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return _sync_single_match(
            match_id=match_id,
            sync_type="fixtures_results",
            syncer=match_list_fixtures_results_syncer,
            cache_prefixes=(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "missing-team-names",
                "paper-recommendation-workspace",
            ),
        )

    @app.post("/api/matches/{match_id}/sync/odds")
    def sync_match_odds(match_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return _sync_single_match(
            match_id=match_id,
            sync_type="odds",
            syncer=match_list_odds_syncer,
            cache_prefixes=(
                "dashboard-summary",
                "league-coverage",
                "match-list-workspace",
                "matches-with-odds",
                "oddspapi-backfill-audit",
                "paper-recommendation-workspace",
            ),
        )

    def _sync_single_match(
        *,
        match_id: int,
        sync_type: str,
        syncer: Callable[[list[int]], dict[str, Any] | str],
        cache_prefixes: tuple[str, ...],
    ) -> dict[str, Any]:
        started_at = clock()
        with session_factory() as session:
            match = session.get(Match, match_id)
            if match is None:
                raise HTTPException(status_code=404, detail="match not found")
            try:
                report = _build_match_sync_report(
                    session=session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    matches=[match],
                    result=syncer([match_id]),
                    display_name_service=display_name_service,
                )
                sync_result = _sync_run_counts_from_report(report)
                run = record_sync_run(
                    session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    status="success",
                    days=0,
                    **sync_result,
                )
                _persist_match_sync_run_items(session, run=run, report=report)
            except Exception as error:
                run = record_sync_run(
                    session,
                    sync_type=sync_type,
                    started_at=started_at,
                    finished_at=clock(),
                    status="failed",
                    days=0,
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    requests_used=0,
                    error_message=str(error),
                )
                raise HTTPException(status_code=500, detail=str(error)) from error
            clear_cache_prefix(*cache_prefixes)
            return {"sync_run": build_data_sync_run_payload(run), "report": report}

    @app.get("/api/data-sync-runs/{run_id}/items")
    def data_sync_run_items(run_id: int) -> dict[str, Any]:
        with session_factory() as session:
            run = session.get(DataSyncRun, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="同步记录不存在")
            return _build_persisted_match_sync_run_payload(
                session=session,
                run=run,
                display_name_service=display_name_service,
            )

    @app.get("/api/matches/{match_id}/odds-trends")
    def match_odds_trends(match_id: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_match_odds_trends(
                session,
                match_id=match_id,
                display_name_service=display_name_service,
            )
            if payload is None:
                raise HTTPException(status_code=404, detail="比赛不存在")
            return payload

    @app.get("/api/matches/{match_id}/detail")
    def match_detail(match_id: int) -> dict[str, Any]:
        with session_factory() as session:
            payload = build_match_detail(
                session,
                match_id=match_id,
                display_name_service=display_name_service,
            )
            if payload is None:
                raise HTTPException(status_code=404, detail="比赛不存在")
            return build_match_detail_payload(payload)

    @app.get("/api/recommendation-records")
    def recommendation_records() -> list[dict[str, Any]]:
        return cached_response(
            ("recommendation-records",),
            lambda: _with_session(
                session_factory,
                lambda session: build_recommendation_records(
                    session,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.get("/api/paper-recommendations/queue")
    def paper_recommendation_queue(
        hours: int = 72,
        near_start_hours: int = 6,
        edge_threshold: str = "0.10",
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        with session_factory() as session:
            report = build_paper_recommendation_queue(
                session,
                now=clock(),
                hours=hours,
                near_start_hours=near_start_hours,
                start_time=_parse_optional_datetime(start_time),
                end_time=_parse_optional_datetime(end_time),
                edge_threshold=edge_threshold,
                scorer=paper_queue_scorer,
                display_name_service=display_name_service,
            )
            return build_paper_recommendation_queue_payload(
                report,
                display_name_service=display_name_service,
            )

    @app.get("/api/paper-recommendations/workspace")
    def paper_recommendation_workspace(
        hours: int = 72,
        near_start_hours: int = 6,
        edge_threshold: str = "0.10",
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        training_fingerprint = _latest_successful_training_fingerprint(session_factory)
        return cached_response(
            (
                "paper-recommendation-workspace",
                hours,
                near_start_hours,
                edge_threshold,
                start_time,
                end_time,
                training_fingerprint,
            ),
            lambda: _with_session(
                session_factory,
                lambda session: _build_paper_recommendation_workspace_response(
                    session,
                    now=clock(),
                    hours=hours,
                    near_start_hours=near_start_hours,
                    start_time=_parse_optional_datetime(start_time),
                    end_time=_parse_optional_datetime(end_time),
                    edge_threshold=edge_threshold,
                    scorer=paper_queue_scorer,
                    display_name_service=display_name_service,
                ),
            ),
        )

    @app.post("/api/paper-recommendations/records")
    def create_paper_recommendation_record(payload: dict[str, Any]) -> dict[str, Any]:
        match_id = int(payload["match_id"])
        strategy_key = payload.get("strategy_key")
        with session_factory() as session:
            queue_report = build_paper_recommendation_queue(
                session,
                now=clock(),
                hours=int(payload.get("hours", 72)),
                near_start_hours=int(payload.get("near_start_hours", 6)),
                start_time=_parse_optional_datetime(payload.get("start_time")),
                end_time=_parse_optional_datetime(payload.get("end_time")),
                edge_threshold=str(payload.get("edge_threshold", "0.10")),
                scorer=paper_queue_scorer,
                display_name_service=display_name_service,
            )
            row = next(
                (
                    item
                    for item in queue_report.rows
                    if item.match_id == match_id
                    and (strategy_key is None or item.strategy_key == strategy_key)
                ),
                None,
            )
            if row is None:
                raise HTTPException(status_code=404, detail="纸面候选不存在")
            try:
                record = create_paper_record_from_queue_row(
                    session,
                    row,
                    recorded_at=clock(),
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            clear_cache_prefix("paper-recommendation-workspace")
            return build_paper_record_payload(record)

    @app.post("/api/paper-recommendations/records/batch")
    def create_paper_recommendation_records_batch(payload: dict[str, Any]) -> dict[str, Any]:
        requested_candidates = payload.get("candidates", [])
        if not isinstance(requested_candidates, list) or not requested_candidates:
            raise HTTPException(status_code=400, detail="paper batch requires candidates")
        skipped_candidates: list[dict[str, Any]] = []
        created_count = 0
        with session_factory() as session:
            queue_report = build_paper_recommendation_queue(
                session,
                now=clock(),
                hours=int(payload.get("hours", 72)),
                near_start_hours=int(payload.get("near_start_hours", 6)),
                start_time=_parse_optional_datetime(payload.get("start_time")),
                end_time=_parse_optional_datetime(payload.get("end_time")),
                edge_threshold=str(payload.get("edge_threshold", "0.10")),
                scorer=paper_queue_scorer,
                display_name_service=display_name_service,
            )
            for item in requested_candidates:
                if not isinstance(item, dict):
                    skipped_candidates.append(
                        {
                            "match_id": None,
                            "strategy_key": None,
                            "reason": "invalid paper candidate payload",
                        }
                    )
                    continue
                strategy_key = item.get("strategy_key")
                try:
                    match_id = int(item["match_id"])
                except (KeyError, TypeError, ValueError):
                    skipped_candidates.append(
                        {
                            "match_id": None,
                            "strategy_key": strategy_key,
                            "reason": "invalid paper candidate match_id",
                        }
                    )
                    continue
                row = next(
                    (
                        candidate
                        for candidate in queue_report.rows
                        if candidate.match_id == match_id
                        and (strategy_key is None or candidate.strategy_key == strategy_key)
                    ),
                    None,
                )
                if row is None:
                    skipped_candidates.append(
                        {
                            "match_id": match_id,
                            "strategy_key": strategy_key,
                            "reason": "纸面候选不存在",
                        }
                    )
                    continue
                try:
                    create_paper_record_from_queue_row(
                        session,
                        row,
                        recorded_at=clock(),
                    )
                except ValueError as error:
                    skipped_candidates.append(
                        {
                            "match_id": match_id,
                            "strategy_key": strategy_key,
                            "reason": str(error),
                        }
                    )
                    continue
                created_count += 1
            if created_count > 0:
                clear_cache_prefix("paper-recommendation-workspace")
            workspace_payload = _build_paper_tracking_workspace_payload_from_queue_report(
                session,
                queue_report,
            )
            workspace_payload["batch_result"] = {
                "requested_count": len(requested_candidates),
                "created_count": created_count,
                "skipped_count": len(skipped_candidates),
                "skipped": skipped_candidates,
            }
            return workspace_payload

    @app.post("/api/paper-recommendations/records/backfill")
    def backfill_paper_recommendation_record(payload: dict[str, Any]) -> dict[str, Any]:
        match_id = int(payload["match_id"])
        with session_factory() as session:
            match = session.get(Match, match_id)
            if match is None:
                raise HTTPException(status_code=404, detail="比赛不存在")
            try:
                record = backfill_paper_record_from_candidate(
                    session,
                    match_id=match_id,
                    recorded_at=_parse_optional_datetime(payload.get("recorded_at")) or clock(),
                    market_line=Decimal(str(payload["market_line"])),
                    odds=Decimal(str(payload["odds"])),
                    model_probability=Decimal(str(payload["model_probability"])),
                    market_probability=Decimal(str(payload["market_probability"])),
                    edge=Decimal(str(payload["edge"])),
                    manual_note=str(payload.get("manual_note") or "历史纸面候选补录"),
                    league_display_name=display_name_service.display_league(match.league.name),
                    home_team_display_name=display_name_service.display_team(
                        match.home_team.canonical_name
                    ),
                    away_team_display_name=display_name_service.display_team(
                        match.away_team.canonical_name
                    ),
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            clear_cache_prefix("paper-recommendation-workspace")
            return build_paper_record_payload(record)

    @app.patch("/api/paper-recommendations/records/{record_id}")
    def edit_paper_recommendation_record(record_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with session_factory() as session:
            try:
                record = edit_paper_record(
                    session,
                    record_id,
                    current_market_line=Decimal(str(payload["current_market_line"])),
                    current_odds=Decimal(str(payload["current_odds"])),
                    manual_note=payload.get("manual_note"),
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            clear_cache_prefix("paper-recommendation-workspace")
            return build_paper_record_payload(record)

    @app.post("/api/paper-recommendations/settle")
    def settle_paper_recommendation_records() -> dict[str, int]:
        with session_factory() as session:
            result = settle_paper_records(session, settled_at=clock())
            clear_cache_prefix("paper-recommendation-workspace")
            return asdict(result)

    @app.post("/api/paper-recommendations/records/{record_id}/void")
    def void_paper_recommendation_record(record_id: int) -> dict[str, Any]:
        with session_factory() as session:
            try:
                record = void_paper_record(session, record_id)
            except ValueError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
            clear_cache_prefix("paper-recommendation-workspace")
            return build_paper_record_payload(record)

    @app.get("/api/training/workspace")
    def training_workspace() -> dict[str, Any]:
        return cached_response(
            ("training-workspace",),
            lambda: _with_session(
                session_factory,
                lambda session: build_training_workspace_payload(
                    baseline_dataset_path=baseline_dataset_path,
                    baseline_dataset_report_path=baseline_dataset_report_path,
                    baseline_qa_report_path=baseline_qa_report_path,
                    baseline_market_report_path=baseline_market_report_path,
                    latest_run=get_latest_training_run(session),
                ),
            ),
        )

    @app.get("/api/training/runs/latest")
    def latest_training_run() -> dict[str, Any] | None:
        with session_factory() as session:
            return build_training_run_payload(get_latest_training_run(session))

    @app.post("/api/training/runs/full-refresh")
    def start_training_full_refresh() -> dict[str, Any]:
        with session_factory() as session:
            try:
                run = create_training_run(session, clock=clock)
                session.commit()
                run_id = run.id
                payload = build_training_run_payload(run)
            except TrainingRunAlreadyRunning as error:
                raise HTTPException(
                    status_code=409,
                    detail={"active_run_id": error.active_run_id},
                ) from error
        clear_cache_prefix("training-workspace")
        training_full_refresh_runner(run_id)
        return payload

    @app.post("/api/training/baseline-dataset")
    def run_training_baseline_dataset() -> dict[str, Any]:
        with session_factory() as session:
            dataset = build_baseline_training_dataset(session)
        write_baseline_training_dataset_csv(dataset, baseline_dataset_path)
        write_baseline_training_dataset_report(dataset.audit, baseline_dataset_report_path)
        clear_cache_prefix("training-workspace")
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    @app.post("/api/training/baseline-dataset-qa")
    def run_training_baseline_dataset_qa() -> dict[str, Any]:
        if not baseline_dataset_path.exists():
            raise HTTPException(status_code=404, detail="baseline dataset csv not found")
        report = build_baseline_training_dataset_qa_report(baseline_dataset_path)
        write_baseline_training_dataset_qa_report(report, baseline_qa_report_path)
        clear_cache_prefix("training-workspace")
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    @app.post("/api/training/market-baseline")
    def run_training_market_baseline() -> dict[str, Any]:
        if not baseline_dataset_path.exists():
            raise HTTPException(status_code=404, detail="baseline dataset csv not found")
        report = build_baseline_training_dataset_market_baseline_report(baseline_dataset_path)
        write_baseline_training_dataset_market_baseline_report(report, baseline_market_report_path)
        clear_cache_prefix("training-workspace")
        return build_training_workspace_payload(
            baseline_dataset_path=baseline_dataset_path,
            baseline_dataset_report_path=baseline_dataset_report_path,
            baseline_qa_report_path=baseline_qa_report_path,
            baseline_market_report_path=baseline_market_report_path,
        )

    return app


def build_dashboard_summary(session: Session) -> dict[str, int]:
    total_matches = session.query(func.count(Match.id)).scalar() or 0
    finished_matches = (
        session.query(func.count(Match.id)).filter(Match.status == "finished").scalar() or 0
    )
    matches_with_historical_odds = (
        session.query(func.count(func.distinct(HistoricalOddsSnapshot.match_id))).scalar() or 0
    )
    historical_odds_snapshots = session.query(func.count(HistoricalOddsSnapshot.id)).scalar() or 0
    unmatched_matches = (
        session.query(func.count(OddsSourceMatch.id))
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .scalar()
        or 0
    )
    return {
        "total_matches": total_matches,
        "finished_matches": finished_matches,
        "matches_with_historical_odds": matches_with_historical_odds,
        "historical_odds_snapshots": historical_odds_snapshots,
        "unmatched_matches": unmatched_matches,
    }


class WebResponseCache:
    def __init__(self, *, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[tuple[Any, ...], tuple[float, Any]] = {}

    def get_or_set(self, key: tuple[Any, ...], builder: Callable[[], Any]) -> Any:
        now = monotonic()
        cached = self._entries.get(key)
        if cached is not None:
            cached_at, value = cached
            if now - cached_at < self.ttl_seconds:
                return value
        value = builder()
        self._entries[key] = (now, value)
        return value

    def clear_prefixes(self, *prefixes: str) -> None:
        if not prefixes:
            self._entries.clear()
            return
        self._entries = {
            key: value
            for key, value in self._entries.items()
            if not key or str(key[0]) not in prefixes
        }


def _with_session(
    session_factory: Callable[[], Session],
    builder: Callable[[Session], Any],
) -> Any:
    with session_factory() as session:
        return builder(session)


def _build_paper_recommendation_workspace_response(
    session: Session,
    *,
    now: datetime,
    hours: int,
    near_start_hours: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    edge_threshold: str,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult] | None,
    display_name_service: DisplayNameService,
) -> dict[str, Any]:
    queue_report = build_paper_recommendation_queue(
        session,
        now=now,
        hours=hours,
        near_start_hours=near_start_hours,
        start_time=start_time,
        end_time=end_time,
        edge_threshold=edge_threshold,
        scorer=scorer,
        display_name_service=display_name_service,
    )
    return _build_paper_tracking_workspace_payload_from_queue_report(session, queue_report)


def _build_paper_tracking_workspace_payload_from_queue_report(
    session: Session,
    queue_report,
) -> dict[str, Any]:
    workspace = build_paper_tracking_workspace(
        session,
        candidates=[row for row in queue_report.rows if row.status == "candidate"],
    )
    payload = build_paper_tracking_workspace_payload(workspace)
    payload["diagnostics"] = build_paper_recommendation_diagnostics_payload(queue_report)
    return payload


def build_league_coverage(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    rows = (
        session.query(
            League.id,
            League.name,
            League.country_or_region,
            Match.season,
            func.count(func.distinct(Match.id)).label("finished_matches"),
            func.count(func.distinct(HistoricalOddsSnapshot.match_id)).label(
                "matches_with_historical_odds"
            ),
        )
        .join(Match, Match.league_id == League.id)
        .outerjoin(HistoricalOddsSnapshot, HistoricalOddsSnapshot.match_id == Match.id)
        .filter(Match.status == "finished")
        .group_by(League.id, League.name, League.country_or_region, Match.season)
        .order_by(League.name.asc(), Match.season.desc())
        .all()
    )
    unmatched_rows = dict(
        session.query(League.id, func.count(OddsSourceMatch.id))
        .join(Match, Match.league_id == League.id)
        .join(OddsSourceMatch, OddsSourceMatch.match_id == Match.id)
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .group_by(League.id)
        .all()
    )
    return [
        {
            "league_id": league_id,
            "league_name": league_name,
            "league_display_name": display_name_service.display_league(league_name),
            "country_or_region": country_or_region,
            "season": season,
            "finished_matches": finished_matches,
            "matches_with_historical_odds": matches_with_historical_odds,
            "coverage_ratio": _format_ratio(matches_with_historical_odds, finished_matches),
            "unmatched_matches": unmatched_rows.get(league_id, 0),
        }
        for (
            league_id,
            league_name,
            country_or_region,
            season,
            finished_matches,
            matches_with_historical_odds,
        ) in rows
    ]


def build_worker_statuses(
    log_dir: Path,
    *,
    process_running_checker: Callable[[int], bool] = _is_process_running,
) -> list[dict[str, Any]]:
    statuses = []
    for status_path in sorted((log_dir / "workers").glob("*.json")):
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        statuses.append(_normalize_worker_status(payload, process_running_checker))
    current_status_path = log_dir / "oddspapi-worker-current.json"
    if current_status_path.exists() and not statuses:
        try:
            statuses.append(
                _normalize_worker_status(
                    json.loads(current_status_path.read_text(encoding="utf-8")),
                    process_running_checker,
                )
            )
        except (OSError, json.JSONDecodeError):
            pass
    return statuses


def build_oddspapi_backfill_audit_payload(
    report: OddsPapiBackfillAuditReport,
) -> dict[str, Any]:
    return {
        "season": report.season,
        "log_dir": str(report.log_dir),
        "worker_progress": (
            asdict(report.worker_progress) if report.worker_progress is not None else None
        ),
        "league_summaries": [asdict(summary) for summary in report.league_summaries],
    }


def build_unmatched_matches(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    rows = (
        session.query(OddsSourceMatch)
        .options(
            joinedload(OddsSourceMatch.match).joinedload(Match.league),
            joinedload(OddsSourceMatch.match).joinedload(Match.home_team),
            joinedload(OddsSourceMatch.match).joinedload(Match.away_team),
        )
        .filter(OddsSourceMatch.historical_odds_status == "unmatched")
        .order_by(OddsSourceMatch.historical_odds_checked_at.desc().nullslast())
        .limit(200)
        .all()
    )
    return [
        {
            **_format_match_names(row.match, display_name_service),
            "source_name": row.source_name,
            "match_reason": row.match_reason,
            "historical_odds_error": row.historical_odds_error,
        }
        for row in rows
    ]


def build_missing_team_display_names(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    return _build_team_display_rows(
        session,
        display_name_service=display_name_service,
        missing_only=True,
        limit=limit,
    )


def _build_team_display_rows(
    session: Session,
    *,
    display_name_service: DisplayNameService,
    league_id: int | None = None,
    season: int | None = None,
    missing_only: bool,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[int, int | None, int], dict[str, Any]] = {}

    for side in ("home", "away"):
        team_id_column = Match.home_team_id if side == "home" else Match.away_team_id
        query = (
            session.query(
                League.id.label("league_id"),
                League.name.label("league_name"),
                Match.season.label("season"),
                Team.id.label("team_id"),
                Team.canonical_name.label("team_name"),
                Team.logo_url.label("team_logo_url"),
                func.count(Match.id).label("match_count"),
                func.max(Match.kickoff_time).label("latest_kickoff_time"),
            )
            .join(Match, Match.league_id == League.id)
            .join(Team, Team.id == team_id_column)
        )
        if league_id is not None:
            query = query.filter(League.id == league_id)
        if season is not None:
            query = query.filter(Match.season == season)
        rows = query.group_by(
            League.id,
            League.name,
            Match.season,
            Team.id,
            Team.canonical_name,
            Team.logo_url,
        ).all()
        for row in rows:
            team_display_name = display_name_service.display_team(row.team_name)
            is_missing_display_name = team_display_name == row.team_name
            if missing_only and not is_missing_display_name:
                continue
            key = (row.league_id, row.season, row.team_id)
            item = rows_by_key.setdefault(
                key,
                {
                    "league_id": row.league_id,
                    "league_name": row.league_name,
                    "league_display_name": display_name_service.display_league(row.league_name),
                    "season": row.season,
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "team_display_name": None if is_missing_display_name else team_display_name,
                    "team_logo_url": row.team_logo_url,
                    "is_missing_display_name": is_missing_display_name,
                    "match_count": 0,
                    "latest_kickoff_time": None,
                    "rank": None,
                    "points": None,
                },
            )
            item["match_count"] += row.match_count
            if item["latest_kickoff_time"] is None or row.latest_kickoff_time > item["latest_kickoff_time"]:
                item["latest_kickoff_time"] = row.latest_kickoff_time

    items = sorted(
        rows_by_key.values(),
        key=lambda item: (
            item["league_display_name"],
            -(item["season"] or 0),
            item["rank"] or 9999,
            -item["match_count"],
            item["team_name"],
        ),
    )
    if limit is not None:
        items = items[:limit]
    return [
        {
            **item,
            "latest_kickoff_time": _format_datetime(item["latest_kickoff_time"]),
        }
        for item in items
    ]


def build_team_display_name_workspace(
    session: Session,
    *,
    league_id: int,
    season: int,
    display_name_service: DisplayNameService | None = None,
    display_translation_status_service: DisplayTranslationStatusService | None = None,
) -> dict[str, Any] | None:
    display_name_service = display_name_service or DisplayNameService()
    display_translation_status_service = (
        display_translation_status_service or DisplayTranslationStatusService()
    )
    league = session.query(League).filter(League.id == league_id).one_or_none()
    if league is None:
        return None
    items = _build_team_display_rows(
        session,
        display_name_service=display_name_service,
        league_id=league_id,
        season=season,
        missing_only=False,
    )
    if not items:
        return None
    return {
        "league_id": league.id,
        "league_name": league.name,
        "league_display_name": display_name_service.display_league(league.name),
        "season": season,
        "is_translation_done": display_translation_status_service.is_done(
            league_id=league_id,
            season=season,
        ),
        "teams": items,
    }


def build_matches_with_odds(
    session: Session,
    *,
    limit: int = 100,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    snapshot_counts = (
        session.query(
            HistoricalOddsSnapshot.match_id.label("match_id"),
            func.count(HistoricalOddsSnapshot.id).label("snapshot_count"),
        )
        .group_by(HistoricalOddsSnapshot.match_id)
        .subquery()
    )
    rows = (
        session.query(Match, snapshot_counts.c.snapshot_count)
        .options(
            joinedload(Match.league),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .join(snapshot_counts, snapshot_counts.c.match_id == Match.id)
        .order_by(Match.kickoff_time.desc(), Match.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            **_format_match_names(match, display_name_service),
            "snapshot_count": snapshot_count,
        }
        for match, snapshot_count in rows
    ]


def build_match_odds_trends(
    session: Session,
    *,
    match_id: int,
    display_name_service: DisplayNameService | None = None,
) -> dict[str, Any] | None:
    display_name_service = display_name_service or DisplayNameService()
    match = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.id == match_id)
        .one_or_none()
    )
    if match is None:
        return None
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .order_by(HistoricalOddsSnapshot.snapshot_time.asc(), HistoricalOddsSnapshot.outcome_side.asc())
        .all()
    )
    return {
        **_format_match_names(match, display_name_service),
        "asian_handicap": _build_market_points(snapshots, market_type="asian_handicap"),
        "total_goals": _build_market_points(snapshots, market_type="total_goals"),
        "match_winner": _build_market_points(snapshots, market_type="match_winner"),
    }


def build_recommendation_records(
    session: Session,
    *,
    display_name_service: DisplayNameService | None = None,
) -> list[dict[str, Any]]:
    display_name_service = display_name_service or DisplayNameService()
    records = (
        session.query(RecommendationRecord)
        .order_by(RecommendationRecord.created_at.desc(), RecommendationRecord.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": record.id,
            "match_id": record.match_id,
            "league_name": record.league_name,
            "league_display_name": display_name_service.display_league(record.league_name),
            "home_team_name": record.home_team_name,
            "home_team_display_name": display_name_service.display_team(record.home_team_name),
            "home_team_logo_url": record.match.home_team.logo_url if record.match else None,
            "away_team_name": record.away_team_name,
            "away_team_display_name": display_name_service.display_team(record.away_team_name),
            "away_team_logo_url": record.match.away_team.logo_url if record.match else None,
            "home_score": record.match.home_score if record.match else None,
            "away_score": record.match.away_score if record.match else None,
            "kickoff_time": _format_datetime(record.kickoff_time),
            "market_type": record.market_type,
            "side": record.side,
            "market_line": _format_decimal(record.market_line, "0.00"),
            "odds": _format_decimal(record.odds, "0.000"),
            "confidence_grade": record.confidence_grade,
            "stake_units": _format_decimal(record.stake_units, "0.00"),
            "status": record.status,
            "settlement_result": record.settlement_result,
            "profit_units": (
                _format_decimal(record.profit_units, "0.000")
                if record.profit_units is not None
                else None
            ),
        }
        for record in records
    ]


def build_paper_recommendation_queue_payload(
    report,
    *,
    display_name_service: DisplayNameService | None = None,
) -> dict[str, Any]:
    display_name_service = display_name_service or DisplayNameService()
    return {
        "generated_at": report.generated_at,
        "window_start": report.window_start,
        "window_end": report.window_end,
        "hours": report.hours,
        "near_start_hours": report.near_start_hours,
        "edge_threshold": str(report.edge_threshold),
        "model_name": report.model_name,
        "total_matches": report.total_matches,
        "candidate_count": report.candidate_count,
        "status_counts": report.status_counts,
        "discarded_by_robustness_match_count": report.discarded_by_robustness_match_count,
        "prefetch_requested": report.prefetch_requested,
        "near_start_fixture_ids": report.near_start_fixture_ids,
        "prefetch_result": report.prefetch_result,
        "rows": [
            {
                "match_id": row.match_id,
                "source_match_id": row.source_match_id,
                "kickoff_time": row.kickoff_time,
                "league_name": row.league_name,
                "league_display_name": row.league_display_name,
                "home_team_name": row.home_team_name,
                "home_team_display_name": row.home_team_display_name,
                "away_team_name": row.away_team_name,
                "away_team_display_name": row.away_team_display_name,
                "status": row.status,
                "market_type": row.market_type,
                "line": _format_optional_decimal(row.line, "0.00"),
                "side": row.side,
                "recommended_handicap": row.recommended_handicap,
                "odds": _format_optional_decimal(row.odds, "0.000"),
                "model_probability": _format_optional_decimal(row.model_probability, "0.0000"),
                "market_probability": _format_optional_decimal(row.market_probability, "0.0000"),
                "edge": _format_optional_decimal(row.edge, "0.0000"),
                "line_bucket": row.line_bucket,
                "risk_tags": list(row.risk_tags),
                "strategy_key": row.strategy_key,
                "strategy_display_name": row.strategy_display_name,
                "signal_version": row.signal_version,
                "odds_source": row.odds_source,
                "execution_target": row.execution_target,
                "historical_snapshot_count": row.historical_snapshot_count,
                "robustness_mode": row.robustness_mode,
                "robustness_status": row.robustness_status,
                "robustness_primary_target": row.robustness_primary_target,
                "robustness_seen_count": row.robustness_seen_count,
                "robustness_min_edge": _format_optional_decimal(row.robustness_min_edge, "0.0000"),
                "robustness_observed_targets": list(row.robustness_observed_targets),
            }
            for row in report.rows
        ],
    }


def build_match_list_workspace_payload(workspace) -> dict[str, Any]:
    return {
        "filters": asdict(workspace.filters),
        "freshness": asdict(workspace.freshness),
        "leagues": workspace.leagues,
        "total_matches": workspace.total_matches,
        "matches": [build_match_list_row_payload(row) for row in workspace.matches],
    }


def build_match_list_row_payload(row) -> dict[str, Any]:
    return {
        "match_id": row.match_id,
        "kickoff_time": row.kickoff_time,
        "league_name": row.league_name,
        "league_display_name": row.league_display_name,
        "home_team_name": row.home_team_name,
        "home_team_display_name": row.home_team_display_name,
        "home_team_logo_url": row.home_team_logo_url,
        "away_team_name": row.away_team_name,
        "away_team_display_name": row.away_team_display_name,
        "away_team_logo_url": row.away_team_logo_url,
        "status": row.status,
        "status_group": row.status_group,
        "home_score": row.home_score,
        "away_score": row.away_score,
        "has_odds": row.has_odds,
        "odds_status_key": row.odds_status_key,
        "odds_status_label": row.odds_status_label,
        "odds_summary": asdict(row.odds_summary),
    }


def build_match_detail_payload(detail) -> dict[str, Any]:
    return {
        "match_id": detail.match_id,
        "kickoff_time": detail.kickoff_time,
        "league_name": detail.league_name,
        "league_display_name": detail.league_display_name,
        "home_team_name": detail.home_team_name,
        "home_team_display_name": detail.home_team_display_name,
        "home_team_logo_url": detail.home_team_logo_url,
        "away_team_name": detail.away_team_name,
        "away_team_display_name": detail.away_team_display_name,
        "away_team_logo_url": detail.away_team_logo_url,
        "status": detail.status,
        "status_group": detail.status_group,
        "home_score": detail.home_score,
        "away_score": detail.away_score,
        "has_odds": detail.has_odds,
        "odds_status_key": detail.odds_status_key,
        "odds_status_label": detail.odds_status_label,
        "team_data_note": detail.team_data_note,
        "odds_summary": asdict(detail.odds_summary),
        "paper_recommendation_summary": asdict(detail.paper_recommendation_summary),
        "formal_recommendation_summary": asdict(detail.formal_recommendation_summary),
    }


def _select_sync_matches_from_payload(
    session: Session,
    payload: dict[str, Any],
    *,
    now: datetime,
) -> list[Match]:
    return select_match_list_sync_targets(
        session,
        now=now,
        start_time=_parse_optional_datetime(payload.get("start_time")),
        end_time=_parse_optional_datetime(payload.get("end_time")),
        league_name=payload.get("league_name") or None,
        status_filter=str(payload.get("status_filter") or "all"),
        odds_filter=str(payload.get("odds_filter") or "all"),
        search=payload.get("search") or None,
    )


def _build_fixture_range_sync_report(
    *,
    sync_type: str,
    started_at: datetime,
    finished_at: datetime,
    result: dict[str, Any] | str,
) -> dict[str, Any]:
    normalized = _normalize_fixture_range_sync_result(result)
    created_count = normalized["created"]
    updated_count = normalized["updated"]
    skipped_count = normalized["skipped"]
    return {
        "sync_type": sync_type,
        "started_at": _format_datetime(started_at),
        "finished_at": _format_datetime(finished_at),
        "target_count": created_count + updated_count + skipped_count,
        "success_count": created_count + updated_count,
        "failed_count": 0,
        "skipped_count": skipped_count,
        "requests_used": normalized["requests"],
        "created_count": created_count,
        "updated_count": updated_count,
        "success": [],
        "failed": [],
        "skipped": [],
    }


def _normalize_fixture_range_sync_result(result: dict[str, Any] | str) -> dict[str, int]:
    if isinstance(result, str):
        parsed = _parse_sync_summary(result)
        return {
            "created": parsed["created"],
            "updated": parsed["updated"],
            "skipped": parsed["skipped"],
            "requests": parsed["requests"],
        }
    return {
        "created": int(result.get("created", result.get("created_count", 0)) or 0),
        "updated": int(result.get("updated", result.get("updated_count", 0)) or 0),
        "skipped": int(result.get("skipped", result.get("skipped_count", 0)) or 0),
        "requests": int(result.get("requests", result.get("requests_used", 0)) or 0),
    }


def _build_match_sync_report(
    *,
    session: Session,
    sync_type: str,
    started_at: datetime,
    finished_at: datetime,
    matches: list[Match],
    result: dict[str, Any] | str,
    display_name_service: DisplayNameService,
) -> dict[str, Any]:
    normalized = _normalize_match_sync_report_result(result)
    match_by_id = {match.id: match for match in matches}
    diagnostic_by_match_id = (
        _build_match_sync_diagnostics(session, match_by_id.keys())
        if sync_type == "odds"
        else {}
    )
    success = _build_match_sync_items(
        session,
        normalized["success"],
        match_by_id=match_by_id,
        diagnostic_by_match_id=diagnostic_by_match_id,
        default_status="success",
        display_name_service=display_name_service,
    )
    failed = _build_match_sync_items(
        session,
        normalized["failed"],
        match_by_id=match_by_id,
        diagnostic_by_match_id=diagnostic_by_match_id,
        default_status="failed",
        display_name_service=display_name_service,
    )
    skipped = _build_match_sync_items(
        session,
        normalized["skipped"],
        match_by_id=match_by_id,
        diagnostic_by_match_id=diagnostic_by_match_id,
        default_status="skipped",
        display_name_service=display_name_service,
    )
    reported_ids = {
        item["match_id"]
        for group in (success, failed, skipped)
        for item in group
        if item.get("match_id") is not None
    }
    for match in matches:
        if match.id not in reported_ids:
            skipped.append(
                _build_match_sync_item_payload(
                    match,
                    status="skipped",
                    message="同步器未返回该场比赛结果",
                    diagnostic=diagnostic_by_match_id.get(match.id, {}),
                    display_name_service=display_name_service,
                )
            )
    return {
        "sync_type": sync_type,
        "started_at": _format_datetime(started_at),
        "finished_at": _format_datetime(finished_at),
        "target_count": len(matches),
        "success_count": len(success),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "requests_used": normalized["requests"],
        "success": success,
        "failed": failed,
        "skipped": skipped,
    }


def _normalize_match_sync_report_result(result: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(result, str):
        parsed = _parse_sync_summary(result)
        return {
            "success": [],
            "failed": [],
            "skipped": [],
            "requests": parsed["requests"],
        }
    return {
        "success": list(result.get("success") or []),
        "failed": list(result.get("failed") or []),
        "skipped": list(result.get("skipped") or []),
        "requests": int(result.get("requests", result.get("requests_used", 0)) or 0),
    }


def _build_match_sync_items(
    session: Session,
    rows: list[Any],
    *,
    match_by_id: dict[int, Match],
    diagnostic_by_match_id: dict[int, dict[str, Any]],
    default_status: str,
    display_name_service: DisplayNameService,
) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        row_payload = row if isinstance(row, dict) else {"match_id": row}
        match_id = int(row_payload["match_id"])
        match = match_by_id.get(match_id) or session.get(Match, match_id)
        if match is None:
            continue
        items.append(
            _build_match_sync_item_payload(
                match,
                status=str(row_payload.get("status") or default_status),
                message=str(row_payload.get("message") or ""),
                diagnostic={
                    **diagnostic_by_match_id.get(match.id, {}),
                    **(row_payload.get("diagnostic") or {}),
                },
                created_count=int(row_payload.get("created_count", row_payload.get("created", 0)) or 0),
                updated_count=int(row_payload.get("updated_count", row_payload.get("updated", 0)) or 0),
                skipped_count=int(row_payload.get("skipped_count", row_payload.get("skipped", 0)) or 0),
                requests_used=int(row_payload.get("requests_used", row_payload.get("requests", 0)) or 0),
                display_name_service=display_name_service,
            )
        )
    return items


def _build_match_sync_item_payload(
    match: Match,
    *,
    status: str,
    message: str,
    diagnostic: dict[str, Any] | None = None,
    display_name_service: DisplayNameService,
    created_count: int = 0,
    updated_count: int = 0,
    skipped_count: int = 0,
    requests_used: int = 0,
) -> dict[str, Any]:
    home_name = match.home_team.canonical_name
    away_name = match.away_team.canonical_name
    home_display = display_name_service.display_team(home_name)
    away_display = display_name_service.display_team(away_name)
    diagnostic = diagnostic or {}
    return {
        "match_id": match.id,
        "kickoff_time": _format_datetime(match.kickoff_time),
        "league_name": match.league.name,
        "league_display_name": display_name_service.display_league(match.league.name),
        "home_team_name": home_name,
        "home_team_display_name": home_display,
        "away_team_name": away_name,
        "away_team_display_name": away_display,
        "fixture": f"{home_display or home_name} vs {away_display or away_name}",
        "status": status,
        "message": message,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "requests_used": requests_used,
        "source_fixture_id": diagnostic.get("source_fixture_id"),
        "diagnostic_status": diagnostic.get("diagnostic_status"),
        "diagnostic_error": diagnostic.get("diagnostic_error"),
        "snapshot_count": int(diagnostic.get("snapshot_count") or 0),
    }


def _build_match_sync_diagnostics(session: Session, match_ids) -> dict[int, dict[str, Any]]:
    ids = [int(match_id) for match_id in match_ids]
    if not ids:
        return {}
    source_rows = {
        row.match_id: row
        for row in session.query(OddsSourceMatch).filter(OddsSourceMatch.match_id.in_(ids)).all()
    }
    snapshot_counts = dict(
        session.query(
            HistoricalOddsSnapshot.match_id,
            func.count(HistoricalOddsSnapshot.id),
        )
        .filter(HistoricalOddsSnapshot.match_id.in_(ids))
        .group_by(HistoricalOddsSnapshot.match_id)
        .all()
    )
    live_snapshot_counts = dict(
        session.query(
            OddsSnapshot.match_id,
            func.count(OddsSnapshot.id),
        )
        .filter(OddsSnapshot.match_id.in_(ids))
        .group_by(OddsSnapshot.match_id)
        .all()
    )
    diagnostics = {}
    for match_id in ids:
        source_row = source_rows.get(match_id)
        historical_snapshot_count = int(snapshot_counts.get(match_id, 0) or 0)
        live_snapshot_count = int(live_snapshot_counts.get(match_id, 0) or 0)
        diagnostics[match_id] = {
            "source_fixture_id": source_row.source_fixture_id if source_row else None,
            "diagnostic_status": (
                source_row.historical_odds_status
                if source_row and historical_snapshot_count > 0
                else ("live_odds_fallback" if live_snapshot_count > 0 else source_row.historical_odds_status if source_row else None)
            ),
            "diagnostic_error": (
                None
                if live_snapshot_count > 0 and historical_snapshot_count == 0
                else source_row.historical_odds_error if source_row else None
            ),
            "snapshot_count": historical_snapshot_count or live_snapshot_count,
        }
    return diagnostics


def _sync_run_counts_from_report(report: dict[str, Any]) -> dict[str, int]:
    return {
        "created_count": int(report["success_count"]),
        "updated_count": 0,
        "skipped_count": int(report["skipped_count"]),
        "requests_used": int(report["requests_used"]),
    }


def _persist_match_sync_run_items(
    session: Session,
    *,
    run: DataSyncRun,
    report: dict[str, Any],
) -> None:
    created_at = run.finished_at or run.started_at
    items = []
    for status_key in ("success", "failed", "skipped"):
        for row in report.get(status_key, []):
            items.append(
                DataSyncRunItem(
                    run_id=run.id,
                    match_id=int(row["match_id"]),
                    sync_type=run.sync_type,
                    status=str(row.get("status") or status_key),
                    message=row.get("message"),
                    created_count=int(row.get("created_count") or 0),
                    updated_count=int(row.get("updated_count") or 0),
                    skipped_count=int(row.get("skipped_count") or 0),
                    requests_used=int(row.get("requests_used") or 0),
                    source_fixture_id=row.get("source_fixture_id"),
                    diagnostic_status=row.get("diagnostic_status"),
                    diagnostic_error=row.get("diagnostic_error"),
                    snapshot_count=int(row.get("snapshot_count") or 0),
                    created_at=created_at,
                )
            )
    session.add_all(items)
    session.commit()


def _build_persisted_match_sync_run_payload(
    *,
    session: Session,
    run: DataSyncRun,
    display_name_service: DisplayNameService,
) -> dict[str, Any]:
    items = (
        session.query(DataSyncRunItem)
        .options(joinedload(DataSyncRunItem.match).joinedload(Match.league))
        .options(joinedload(DataSyncRunItem.match).joinedload(Match.home_team))
        .options(joinedload(DataSyncRunItem.match).joinedload(Match.away_team))
        .filter(DataSyncRunItem.run_id == run.id)
        .order_by(DataSyncRunItem.id.asc())
        .all()
    )
    groups = {"success": [], "failed": [], "skipped": []}
    for item in items:
        diagnostic = (
            {
                "source_fixture_id": item.source_fixture_id,
                "diagnostic_status": item.diagnostic_status,
                "diagnostic_error": item.diagnostic_error,
                "snapshot_count": item.snapshot_count,
            }
            if run.sync_type == "odds"
            else {}
        )
        payload = _build_match_sync_item_payload(
            item.match,
            status=item.status,
            message=item.message or "",
            diagnostic=diagnostic,
            created_count=item.created_count,
            updated_count=item.updated_count,
            skipped_count=item.skipped_count,
            requests_used=item.requests_used,
            display_name_service=display_name_service,
        )
        if item.status in groups:
            groups[item.status].append(payload)
        else:
            groups["failed"].append(payload)
    report = {
        "sync_type": run.sync_type,
        "started_at": _format_datetime(run.started_at),
        "finished_at": _format_datetime(run.finished_at),
        "target_count": len(items),
        "success_count": len(groups["success"]),
        "failed_count": len(groups["failed"]),
        "skipped_count": len(groups["skipped"]),
        "requests_used": run.requests_used,
        **groups,
    }
    if run.sync_type == "fixtures_range":
        report.update(
            {
                "target_count": run.created_count + run.updated_count + run.skipped_count,
                "success_count": run.created_count + run.updated_count,
                "skipped_count": run.skipped_count,
                "created_count": run.created_count,
                "updated_count": run.updated_count,
            }
        )
    return {"sync_run": build_data_sync_run_payload(run), "report": report}


def build_data_sync_run_payload(run: DataSyncRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "sync_type": run.sync_type,
        "started_at": _format_datetime(run.started_at),
        "finished_at": _format_datetime(run.finished_at),
        "status": run.status,
        "days": run.days,
        "created_count": run.created_count,
        "updated_count": run.updated_count,
        "skipped_count": run.skipped_count,
        "requests_used": run.requests_used,
        "error_message": run.error_message,
    }


def _latest_successful_training_fingerprint(session_factory: Callable[[], Session]) -> tuple[int, str] | None:
    with session_factory() as session:
        run = (
            session.query(TrainingRun)
            .filter(TrainingRun.run_type == "full_refresh")
            .filter(TrainingRun.status == "success")
            .filter(TrainingRun.dynamic_feature_path.isnot(None))
            .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
            .first()
        )
        if run is None or not run.dynamic_feature_path:
            return None
        return (run.id, run.dynamic_feature_path)


def build_paper_tracking_workspace_payload(workspace) -> dict[str, Any]:
    return {
        "strategies": [
            {
                "strategy_key": strategy.strategy_key,
                "display_name": strategy.display_name,
                "market_type": strategy.market_type,
                "side": strategy.side,
                "edge_threshold": _format_decimal(strategy.edge_threshold, "0.0000"),
                "model_name": strategy.model_name,
                "signal_version": strategy.signal_version,
            }
            for strategy in workspace.strategies
        ],
        "candidates": [
            {
                "match_id": row.match_id,
                "source_match_id": row.source_match_id,
                "kickoff_time": row.kickoff_time,
                "league_name": row.league_name,
                "league_display_name": row.league_display_name,
                "home_team_name": row.home_team_name,
                "home_team_display_name": row.home_team_display_name,
                "away_team_name": row.away_team_name,
                "away_team_display_name": row.away_team_display_name,
                "status": row.status,
                "market_type": row.market_type,
                "side": row.side,
                "recommended_handicap": row.recommended_handicap,
                "line": _format_optional_decimal(row.line, "0.00"),
                "odds": _format_optional_decimal(row.odds, "0.000"),
                "model_probability": _format_optional_decimal(row.model_probability, "0.0000"),
                "market_probability": _format_optional_decimal(row.market_probability, "0.0000"),
                "edge": _format_optional_decimal(row.edge, "0.0000"),
                "line_bucket": row.line_bucket,
                "risk_tags": list(row.risk_tags),
                "strategy_key": row.strategy_key,
                "strategy_display_name": row.strategy_display_name,
                "signal_version": row.signal_version,
                "odds_source": row.odds_source,
                "execution_target": row.execution_target,
                "historical_snapshot_count": row.historical_snapshot_count,
                "robustness_mode": row.robustness_mode,
                "robustness_status": row.robustness_status,
                "robustness_primary_target": row.robustness_primary_target,
                "robustness_seen_count": row.robustness_seen_count,
                "robustness_min_edge": _format_optional_decimal(row.robustness_min_edge, "0.0000"),
                "robustness_observed_targets": list(row.robustness_observed_targets),
                "is_recordable": row.status == "candidate",
            }
            for row in workspace.candidates
        ],
        "records": [build_paper_record_payload(record) for record in workspace.records],
        "summary": build_paper_summary_payload(workspace.summary),
        "groups": {
            "by_strategy": [build_paper_group_payload(group) for group in workspace.by_strategy],
            "by_league": [build_paper_group_payload(group) for group in workspace.by_league],
            "by_line_bucket": [build_paper_group_payload(group) for group in workspace.by_line_bucket],
            "by_manual_adjustment": [
                build_paper_group_payload(group) for group in workspace.by_manual_adjustment
            ],
        },
        "confidence_simulation": build_paper_confidence_workspace_payload(
            build_paper_confidence_workspace(workspace.records)
        ),
    }


def build_paper_confidence_workspace_payload(workspace) -> dict[str, Any]:
    return {
        "summary": build_paper_confidence_summary_payload(workspace.summary),
        "groups": [build_paper_confidence_group_payload(group) for group in workspace.groups],
        "by_score_bucket": [
            build_paper_confidence_group_summary_payload(group)
            for group in workspace.by_score_bucket
        ],
        "by_stake_bucket": [
            build_paper_confidence_group_summary_payload(group)
            for group in workspace.by_stake_bucket
        ],
        "by_family_combo": [
            build_paper_confidence_group_summary_payload(group)
            for group in workspace.by_family_combo
        ],
    }


def build_paper_confidence_summary_payload(summary) -> dict[str, Any]:
    return {
        "group_count": summary.group_count,
        "settled_groups": summary.settled_groups,
        "suggested_stake_units": _format_decimal(summary.suggested_stake_units, "0.00"),
        "flat_profit_units": _format_decimal(summary.flat_profit_units, "0.000"),
        "weighted_profit_units": _format_decimal(summary.weighted_profit_units, "0.000"),
        "flat_roi": _format_decimal(summary.flat_roi, "0.0000"),
        "weighted_roi": _format_decimal(summary.weighted_roi, "0.0000"),
    }


def build_paper_confidence_group_summary_payload(summary) -> dict[str, Any]:
    return {
        "group_name": summary.group_name,
        "group_count": summary.group_count,
        "settled_groups": summary.settled_groups,
        "suggested_stake_units": _format_decimal(summary.suggested_stake_units, "0.00"),
        "flat_profit_units": _format_decimal(summary.flat_profit_units, "0.000"),
        "weighted_profit_units": _format_decimal(summary.weighted_profit_units, "0.000"),
        "flat_roi": _format_decimal(summary.flat_roi, "0.0000"),
        "weighted_roi": _format_decimal(summary.weighted_roi, "0.0000"),
    }


def build_paper_confidence_group_payload(group) -> dict[str, Any]:
    return {
        "group_key": group.group_key,
        "match_id": group.match_id,
        "source_match_id": group.source_match_id,
        "kickoff_time": _format_datetime(group.kickoff_time),
        "league_name": group.league_name,
        "league_display_name": group.league_display_name,
        "home_team_name": group.home_team_name,
        "home_team_display_name": group.home_team_display_name,
        "home_team_logo_url": group.home_team_logo_url,
        "away_team_name": group.away_team_name,
        "away_team_display_name": group.away_team_display_name,
        "away_team_logo_url": group.away_team_logo_url,
        "home_score": group.home_score,
        "away_score": group.away_score,
        "market_type": group.market_type,
        "logical_side": group.logical_side,
        "recommendation_text": group.recommendation_text,
        "representative_record_id": group.representative_record_id,
        "representative_strategy_key": group.representative_strategy_key,
        "representative_market_line": _format_decimal(group.representative_market_line, "0.00"),
        "representative_odds": _format_decimal(group.representative_odds, "0.000"),
        "signal_record_ids": list(group.signal_record_ids),
        "triggered_strategy_keys": list(group.triggered_strategy_keys),
        "triggered_strategy_display_names": list(group.triggered_strategy_display_names),
        "signal_families": list(group.signal_families),
        "confidence_score": group.confidence_score,
        "suggested_stake_units": _format_decimal(group.suggested_stake_units, "0.00"),
        "stake_cap_reason": group.stake_cap_reason,
        "status": group.status,
        "settlement_result": group.settlement_result,
        "flat_profit_units": _format_decimal(group.flat_profit_units, "0.000"),
        "weighted_profit_units": _format_decimal(group.weighted_profit_units, "0.000"),
        "warning": group.warning,
    }


def build_paper_recommendation_diagnostics_payload(report) -> dict[str, Any]:
    return {
        "total_matches": report.total_matches,
        "candidate_count": report.candidate_count,
        "candidate_match_count": len(
            {row.match_id for row in report.rows if row.status == "candidate"}
        ),
        "status_counts": report.status_counts,
        "edge_threshold": _format_decimal(report.edge_threshold, "0.0000"),
        "discarded_by_robustness_match_count": report.discarded_by_robustness_match_count,
    }


def build_paper_record_payload(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "match_id": record.match_id,
        "source_match_id": record.source_match_id,
        "created_at": _format_datetime(record.created_at),
        "updated_at": _format_datetime(record.updated_at),
        "kickoff_time": _format_datetime(record.kickoff_time),
        "league_name": record.league_name,
        "league_display_name": record.league_display_name,
        "home_team_name": record.home_team_name,
        "home_team_display_name": record.home_team_display_name,
        "home_team_logo_url": record.match.home_team.logo_url if record.match else None,
        "away_team_name": record.away_team_name,
        "away_team_display_name": record.away_team_display_name,
        "away_team_logo_url": record.match.away_team.logo_url if record.match else None,
        "home_score": record.match.home_score if record.match else None,
        "away_score": record.match.away_score if record.match else None,
        "strategy_key": record.strategy_key,
        "strategy_display_name": record.strategy_display_name,
        "model_name": record.model_name,
        "signal_version": record.signal_version,
        "market_type": record.market_type,
        "side": record.side,
        "recommended_handicap": record.recommended_handicap,
        "original_recommended_handicap": record.original_recommended_handicap,
        "line_bucket": record.line_bucket,
        "risk_tags": _split_tags(record.risk_tags),
        "original_market_line": _format_decimal(record.original_market_line, "0.00"),
        "original_odds": _format_decimal(record.original_odds, "0.000"),
        "current_market_line": _format_decimal(record.current_market_line, "0.00"),
        "current_odds": _format_decimal(record.current_odds, "0.000"),
        "model_probability": _format_optional_decimal(record.model_probability, "0.0000"),
        "market_probability": _format_optional_decimal(record.market_probability, "0.0000"),
        "edge": _format_decimal(record.edge, "0.0000"),
        "stake_units": _format_decimal(record.stake_units, "0.00"),
        "status": record.status,
        "is_manually_adjusted": record.is_manually_adjusted,
        "manual_note": record.manual_note,
        "settlement_result": record.settlement_result,
        "profit_units": (
            _format_decimal(record.profit_units, "0.000")
            if record.profit_units is not None
            else None
        ),
        "settled_at": _format_datetime(record.settled_at),
    }


def build_paper_summary_payload(summary) -> dict[str, Any]:
    return {
        "total_records": summary.total_records,
        "pending_records": summary.pending_records,
        "settled_records": summary.settled_records,
        "void_records": summary.void_records,
        "candidate_count": summary.candidate_count,
        "total_stake_units": _format_decimal(summary.total_stake_units, "0.00"),
        "total_profit_units": _format_decimal(summary.total_profit_units, "0.000"),
        "hit_rate": _format_decimal(summary.hit_rate, "0.0000"),
        "roi": _format_decimal(summary.roi, "0.0000"),
    }


def build_paper_group_payload(group) -> dict[str, Any]:
    return {
        "group_name": group.group_name,
        "record_count": group.record_count,
        "settled_records": group.settled_records,
        "total_stake_units": _format_decimal(group.total_stake_units, "0.00"),
        "total_profit_units": _format_decimal(group.total_profit_units, "0.000"),
        "hit_rate": _format_decimal(group.hit_rate, "0.0000"),
        "roi": _format_decimal(group.roi, "0.0000"),
    }


def build_training_workspace_payload(
    *,
    baseline_dataset_path: Path,
    baseline_dataset_report_path: Path,
    baseline_qa_report_path: Path,
    baseline_market_report_path: Path,
    latest_run: TrainingRun | None = None,
) -> dict[str, Any]:
    dataset_payload = _build_training_dataset_file_payload(baseline_dataset_path)
    qa_payload: dict[str, Any] = {
        "exists": baseline_qa_report_path.exists(),
        "path": str(baseline_qa_report_path),
        "updated_at": _format_file_mtime(baseline_qa_report_path),
        "empty_required_cells": 0,
        "invalid_odds_cells": 0,
        "invalid_probability_cells": 0,
        "invalid_overround_cells": 0,
        "thin_history_count": 0,
        "thin_history_ratio": "0.0000",
        "low_sample_leagues": {},
    }
    if baseline_dataset_path.exists():
        qa_report = build_baseline_training_dataset_qa_report(baseline_dataset_path)
        qa_payload = {
            "exists": baseline_qa_report_path.exists(),
            "path": str(baseline_qa_report_path),
            "updated_at": _format_file_mtime(baseline_qa_report_path),
            "empty_required_cells": sum(qa_report.empty_required_cells.values()),
            "invalid_odds_cells": sum(qa_report.invalid_odds_cells.values()),
            "invalid_probability_cells": sum(qa_report.invalid_probability_cells.values()),
            "invalid_overround_cells": sum(qa_report.invalid_overround_cells.values()),
            "thin_history_count": qa_report.thin_history_count,
            "thin_history_ratio": qa_report.thin_history_ratio,
            "low_sample_leagues": qa_report.low_sample_leagues,
        }

    market_payload: dict[str, Any] = {
        "exists": baseline_market_report_path.exists(),
        "path": str(baseline_market_report_path),
        "updated_at": _format_file_mtime(baseline_market_report_path),
        "market_samples": 0,
        "evaluated_market_samples": 0,
        "skipped_market_samples": 0,
        "market_reports": {},
    }
    if baseline_dataset_path.exists():
        market_report = build_baseline_training_dataset_market_baseline_report(
            baseline_dataset_path
        )
        market_payload = {
            "exists": baseline_market_report_path.exists(),
            "path": str(baseline_market_report_path),
            "updated_at": _format_file_mtime(baseline_market_report_path),
            "market_samples": market_report.total_market_samples,
            "evaluated_market_samples": market_report.total_evaluated_market_samples,
            "skipped_market_samples": market_report.total_skipped_market_samples,
            "market_reports": {
                market_type: {
                    "evaluated_count": report.evaluated_count,
                    "skipped_count": report.skipped_count,
                    "accuracy": str(report.accuracy),
                    "log_loss": str(report.average_log_loss),
                    "brier": str(report.average_brier_score),
                    "overround": str(report.average_overround),
                    "flat_bet_profit_units": str(report.flat_bet_profit_units),
                    "flat_bet_roi": str(report.flat_bet_roi),
                    "predicted_side_counts": report.predicted_side_counts,
                }
                for market_type, report in market_report.market_reports.items()
            },
        }

    return {
        "dataset": dataset_payload,
        "dataset_report": _build_report_file_payload(baseline_dataset_report_path),
        "qa": qa_payload,
        "market_baseline": market_payload,
        "latest_run": build_training_run_payload(latest_run),
    }


def build_training_run_payload(run: TrainingRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    signal_research_paths = _training_signal_research_report_paths(run)
    artifact_paths = {
        "dataset_path": run.dataset_path,
        "dataset_report_path": run.dataset_report_path,
        "qa_report_path": run.qa_report_path,
        "market_baseline_report_path": run.market_baseline_report_path,
        "feature_path": run.feature_path,
        "feature_report_path": run.feature_report_path,
        "dynamic_feature_path": run.dynamic_feature_path,
        "dynamic_feature_report_path": run.dynamic_feature_report_path,
        "away_cover_stability_report_path": run.away_cover_stability_report_path,
        "away_cover_bucket_threshold_report_path": run.away_cover_bucket_threshold_report_path,
        "away_cover_bucket_sandbox_report_path": run.away_cover_bucket_sandbox_report_path,
        "total_goals_edge_stability_report_path": run.total_goals_edge_stability_report_path,
        "total_goals_bucket_sandbox_report_path": run.total_goals_bucket_sandbox_report_path,
        **signal_research_paths,
    }
    return {
        "id": run.id,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": _format_datetime(run.started_at),
        "finished_at": _format_datetime(run.finished_at),
        "snapshot_tag": run.snapshot_tag,
        "current_step": run.current_step,
        "error_step": run.error_step,
        "error_message": run.error_message,
        "dataset_rows": run.dataset_rows,
        "eligible_matches": run.eligible_matches,
        "complete_matches": run.complete_matches,
        "coverage_ratio": (
            _format_decimal(run.coverage_ratio, "0.0000")
            if run.coverage_ratio is not None
            else None
        ),
        "last_trained_match_id": run.last_trained_match_id,
        "last_trained_match_summary": run.last_trained_match_summary,
        "last_trained_kickoff_time": _format_datetime(run.last_trained_kickoff_time),
        "new_complete_matches": run.new_complete_matches,
        "artifact_paths": artifact_paths,
    }


def _training_signal_research_report_paths(run: TrainingRun) -> dict[str, str]:
    snapshot_paths = build_training_snapshot_paths(Path("."), run.snapshot_tag)
    base_path = (
        Path(run.away_cover_stability_report_path)
        if run.away_cover_stability_report_path
        else snapshot_paths.away_cover_stability_report_path
    )
    return {
        "total_goals_v3_signal_research_report_path": str(
            base_path.with_name(
                snapshot_paths.experiment_report_paths["total_goals_v3_signal_research"].name
            )
        ),
        "model_consensus_signal_research_report_path": str(
            base_path.with_name(
                snapshot_paths.experiment_report_paths["model_consensus_signal_research"].name
            )
        ),
    }


def _start_training_full_refresh_thread(
    session_factory: Callable[[], Session],
    run_id: int,
    *,
    display_name_service: DisplayNameService,
    clock: Callable[[], datetime],
) -> None:
    thread = Thread(
        target=run_training_full_refresh,
        args=(session_factory, run_id),
        kwargs={
            "display_league": display_name_service.display_league,
            "display_team": display_name_service.display_team,
            "clock": clock,
        },
        daemon=True,
    )
    thread.start()


def _run_match_list_fixtures_results_sync(match_ids: list[int]) -> dict[str, Any]:
    if not match_ids:
        return {"success": [], "failed": [], "skipped": [], "requests": 0}
    provider = None
    success = []
    failed = []
    skipped = []
    with _open_session_for_web_sync() as session:
        for match_id in match_ids:
            match = session.get(Match, match_id)
            if match is None or not match.source_match_id:
                skipped.append({"match_id": match_id, "message": "缺少 API-Football fixture id"})
                continue
            if _is_live_match_for_result_sync(match, now=now_beijing()):
                skipped.append({"match_id": match_id, "message": "比赛进行中，暂不申请赛果"})
                continue
            try:
                if provider is None:
                    settings = load_project_settings()
                    provider = build_api_football_provider(settings)
                payload = provider.client.get(
                    "fixtures",
                    {
                        "id": match.source_match_id,
                        "timezone": "Asia/Shanghai",
                    },
                )
                result = upsert_fixtures(session, map_fixtures(payload))
                success.append(
                    {
                        "match_id": match_id,
                        "message": "赛程/赛果已刷新",
                        "created": result.created_matches,
                        "updated": result.updated_matches,
                        "requests": 1,
                    }
                )
            except Exception as error:
                failed.append({"match_id": match_id, "message": str(error)})
    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "requests": provider.client.request_count if provider is not None else 0,
    }


def _run_match_list_fixture_range_sync(
    start_time: datetime,
    end_time: datetime,
    league_name: str | None = None,
) -> dict[str, Any]:
    start_time = _as_beijing_datetime(start_time)
    end_time = _as_beijing_datetime(end_time)
    settings = load_project_settings()
    provider = build_api_football_provider(settings)
    enabled_league_ids = {
        str(league.api_football_id)
        for league in settings.leagues
        if league.enabled
    }
    configured_league_names_by_id = {
        str(league.api_football_id): league.name
        for league in settings.leagues
    }
    fixtures = []
    seen_match_ids: set[str] = set()
    query_date = start_time.date()
    while query_date <= end_time.date():
        payload = provider.client.get(
            "fixtures",
            {
                "date": query_date.isoformat(),
                "timezone": "Asia/Shanghai",
            },
        )
        for fixture in map_fixtures(payload):
            if fixture.source_league_id not in enabled_league_ids:
                continue
            if fixture.source_match_id in seen_match_ids:
                continue
            kickoff_time = _as_beijing_datetime(fixture.kickoff_time)
            if kickoff_time < start_time or kickoff_time > end_time:
                continue
            if league_name and not _fixture_matches_league_filter(
                fixture_league_name=fixture.league_name,
                fixture_country=fixture.country,
                configured_league_name=configured_league_names_by_id.get(fixture.source_league_id),
                league_name=league_name,
            ):
                continue
            seen_match_ids.add(fixture.source_match_id)
            fixtures.append(fixture)
        query_date += timedelta(days=1)
    with _open_session_for_web_sync() as session:
        result = upsert_fixtures(session, fixtures)
    return {
        "created": result.created_matches,
        "updated": result.updated_matches,
        "skipped": 0,
        "requests": provider.client.request_count,
    }


def _fixture_matches_league_filter(
    *,
    fixture_league_name: str,
    fixture_country: str,
    configured_league_name: str | None,
    league_name: str,
) -> bool:
    candidates = {
        fixture_league_name,
        league_internal_name(fixture_league_name, fixture_country),
    }
    if configured_league_name:
        candidates.add(configured_league_name)
    return league_name in candidates


def _is_live_match_for_result_sync(match: Match, *, now: datetime | None = None) -> bool:
    live_values = {"live", "in_play", "halftime", "1h", "2h", "ht", "et", "bt", "p", "int", "susp"}
    status_values = {
        str(value).strip().lower()
        for value in (match.status, match.status_short, match.status_long)
        if value
    }
    if not status_values & live_values:
        return False
    now = now or now_beijing()
    kickoff_time = match.kickoff_time
    if kickoff_time.tzinfo is None:
        kickoff_time = kickoff_time.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE))
    return now - kickoff_time < timedelta(hours=2)


def _run_match_list_odds_sync(match_ids: list[int]) -> dict[str, Any]:
    if not match_ids:
        return {"success": [], "failed": [], "skipped": [], "requests": 0}
    with _open_session_for_web_sync() as session:
        matches = session.query(Match).filter(Match.id.in_(match_ids)).all()
        seasons = sorted({match.season for match in matches if match.season is not None})
    if not seasons:
        return {
            "success": [],
            "failed": [],
            "skipped": [{"match_id": match_id, "message": "缺少赛季"} for match_id in match_ids],
            "requests": 0,
        }
    success_ids: set[int] = set()
    failed_ids: set[int] = set()
    skipped = []
    fallback_errors: dict[int, str] = {}
    requests_used = 0
    for season in seasons:
        season_match_ids = {
            match.id for match in matches if match.season == season
        }
        if not season_match_ids:
            continue
        result = run_oddspapi_sync_result(
            season=season,
            max_matches=len(season_match_ids),
            request_budget=max(50, len(season_match_ids) * 20),
            timeout_seconds=40,
            max_snapshots_per_match=151,
            match_ids=season_match_ids,
            historical_odds_cooldown_seconds=7.5,
            refresh_pre_kickoff_existing=True,
        )
        requests_used += result.requests_used
        with _open_session_for_web_sync() as session:
            missing_live_odds_fixture_ids = _select_live_odds_fallback_fixture_ids(
                session,
                season_match_ids,
            )
        if missing_live_odds_fixture_ids:
            provider = build_api_football_provider(load_project_settings())
            with _open_session_for_web_sync() as session:
                for fixture_id in missing_live_odds_fixture_ids:
                    try:
                        snapshots = provider.fetch_odds_for_fixtures([fixture_id])
                    except ApiFootballApiError as exc:
                        match_id = _match_id_for_source_fixture_id(
                            session,
                            fixture_id,
                            season_match_ids,
                        )
                        if match_id is not None:
                            fallback_errors[match_id] = str(exc)
                        continue
                    upsert_odds_snapshots(session, snapshots)
            requests_used += provider.client.request_count
        with _open_session_for_web_sync() as session:
            for match_id in season_match_ids:
                has_historical_odds = (
                    session.query(HistoricalOddsSnapshot)
                    .filter_by(match_id=match_id, source_name="oddspapi")
                    .first()
                    is not None
                )
                has_live_odds = (
                    session.query(OddsSnapshot)
                    .filter_by(match_id=match_id)
                    .first()
                    is not None
                )
                if has_historical_odds or has_live_odds:
                    success_ids.add(match_id)
                else:
                    failed_ids.add(match_id)
    return {
        "success": [
            {"match_id": match_id, "message": "赔率已刷新"}
            for match_id in sorted(success_ids)
        ],
        "failed": [
            {"match_id": match_id, "message": fallback_errors.get(match_id) or "未获取到可用赔率"}
            for match_id in sorted(failed_ids - success_ids)
        ],
        "skipped": skipped,
        "requests": requests_used,
    }


def _match_id_for_source_fixture_id(
    session: Session,
    source_fixture_id: str,
    match_ids: set[int],
) -> int | None:
    row = (
        session.query(Match.id)
        .filter(Match.id.in_(match_ids))
        .filter(Match.source_match_id == source_fixture_id)
        .one_or_none()
    )
    return int(row[0]) if row is not None else None


def _select_live_odds_fallback_fixture_ids(session: Session, match_ids: set[int]) -> list[str]:
    if not match_ids:
        return []
    matches = (
        session.query(Match)
        .filter(Match.id.in_(match_ids))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )
    fixture_ids = []
    for match in matches:
        if match.source_match_id is None:
            continue
        if not _is_not_started_match(match):
            continue
        kickoff_time = match.kickoff_time
        if kickoff_time.tzinfo is None:
            kickoff_time = kickoff_time.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE))
        if kickoff_time <= now_beijing():
            continue
        has_historical_odds = (
            session.query(HistoricalOddsSnapshot)
            .filter_by(match_id=match.id, source_name="oddspapi")
            .first()
            is not None
        )
        if has_historical_odds:
            continue
        fixture_ids.append(match.source_match_id)
    return fixture_ids


def _is_not_started_match(match: Match) -> bool:
    values = {
        str(value).strip().lower()
        for value in (match.status, match.status_short, match.status_long)
        if value
    }
    return not values or bool(values & {"scheduled", "ns", "not started"})


def _open_session_for_web_sync():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def _parse_sync_summary(summary: str) -> dict[str, int]:
    values = {"created": 0, "updated": 0, "skipped": 0, "requests": 0}
    for part in summary.replace(",", "").split():
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        if key in values:
            try:
                values[key] = int(raw_value)
            except ValueError:
                values[key] = 0
    return values


def _parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _as_beijing_datetime(value: datetime) -> datetime:
    timezone = ZoneInfo(BEIJING_TIMEZONE)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def _build_training_dataset_file_payload(path: Path) -> dict[str, Any]:
    payload = _build_report_file_payload(path)
    payload.update({"row_count": 0, "column_count": 0})
    if not path.exists():
        return payload
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        row_count = sum(1 for _ in reader)
        column_count = len(reader.fieldnames or [])
    payload.update({"row_count": row_count, "column_count": column_count})
    return payload


def _build_report_file_payload(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "path": str(path),
        "updated_at": _format_file_mtime(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def _format_file_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def _build_market_points(
    snapshots: list[HistoricalOddsSnapshot],
    *,
    market_type: str,
) -> list[dict[str, str]]:
    grouped: dict[tuple[datetime, Decimal, str], dict[str, str]] = defaultdict(dict)
    for snapshot in snapshots:
        if snapshot.market_type != market_type:
            continue
        key = (snapshot.snapshot_time, snapshot.market_line, snapshot.bookmaker)
        point = grouped[key]
        point["snapshot_time"] = _format_historical_odds_datetime(snapshot.snapshot_time)
        point["bookmaker"] = snapshot.bookmaker
        point["market_line"] = _format_decimal(snapshot.market_line, "0.00")
        if market_type == "asian_handicap":
            if snapshot.outcome_side == "home":
                point["home_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "away":
                point["away_odds"] = _format_decimal(snapshot.odds, "0.000")
        if market_type == "total_goals":
            if snapshot.outcome_side == "over":
                point["over_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "under":
                point["under_odds"] = _format_decimal(snapshot.odds, "0.000")
        if market_type == "match_winner":
            if snapshot.outcome_side == "home":
                point["home_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "draw":
                point["draw_odds"] = _format_decimal(snapshot.odds, "0.000")
            if snapshot.outcome_side == "away":
                point["away_odds"] = _format_decimal(snapshot.odds, "0.000")
    return list(grouped.values())


def _normalize_worker_status(
    payload: dict[str, Any],
    process_running_checker: Callable[[int], bool],
) -> dict[str, Any]:
    pid = int(payload.get("pid") or 0)
    return {
        "pid": pid,
        "started_at": payload.get("started_at"),
        "status": payload.get("status", "unknown"),
        "runtime_status": "running" if process_running_checker(pid) else "stopped",
        "mode": payload.get("mode"),
        "season": payload.get("season"),
        "league_ids": payload.get("league_ids") or [],
        "process_log_path": payload.get("process_log_path"),
        "worker_log_dir": payload.get("worker_log_dir"),
        "notify_on_complete": bool(payload.get("notify_on_complete", False)),
    }


def _format_match_names(match: Match, display_name_service: DisplayNameService) -> dict[str, Any]:
    league_name = match.league.name
    home_team_name = match.home_team.canonical_name
    away_team_name = match.away_team.canonical_name
    return {
        "match_id": match.id,
        "league_name": league_name,
        "league_display_name": display_name_service.display_league(league_name),
        "home_team_name": home_team_name,
        "home_team_display_name": display_name_service.display_team(home_team_name),
        "away_team_name": away_team_name,
        "away_team_display_name": display_name_service.display_team(away_team_name),
        "kickoff_time": _format_datetime(match.kickoff_time),
    }


def _format_ratio(count: int, total: int) -> str:
    if total == 0:
        return "0.0000"
    return str((Decimal(count) / Decimal(total)).quantize(Decimal("0.0000")))


def _format_decimal(value: Decimal, pattern: str) -> str:
    return str(Decimal(value).quantize(Decimal(pattern)))


def _format_optional_decimal(value: Decimal | None, pattern: str) -> str | None:
    if value is None:
        return None
    return _format_decimal(value, pattern)


def _split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(",") if item]


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_historical_odds_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(BEIJING_TIMEZONE)).isoformat()

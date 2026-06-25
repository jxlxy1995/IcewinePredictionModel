from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import date, datetime, time as datetime_time, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy.orm import Session
from sqlalchemy import func

from icewine_prediction.alias_service import list_external_aliases
from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.dynamic_main_market_service import (
    build_dynamic_main_market_snapshots,
    build_dynamic_neighbor_market_snapshots,
)
from icewine_prediction.historical_odds_service import (
    match_snapshot_timeline_kickoff_time,
    store_historical_odds_raw_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, Match, OddsSourceMatch
from icewine_prediction.odds_source_match_service import (
    ExternalAliasInput,
    OddsPapiFixture,
    find_best_odds_source_match,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.oddspapi_client import (
    OddsPapiApiError,
    OddsPapiClient,
    OddsPapiRequestBudgetExceededError,
)
from icewine_prediction.sources.oddspapi_market_mapper import map_markets
from icewine_prediction.sources.oddspapi_odds_mapper import map_historical_odds
from icewine_prediction.time_utils import now_beijing

ODDSPAPI_BASE_URL = "https://api.oddspapi.io/v4"
ODDSPAPI_SOURCE_NAME = "oddspapi"
SOCCER_SPORT_ID = 10
SELECTED_BOOKMAKERS = "pinnacle"
DEFAULT_BOOKMAKER = "pinnacle"
TERMINAL_HISTORICAL_ODDS_STATUSES = {"empty", "unavailable", "unmatched"}
HISTORICAL_ODDS_TIMEOUT_ATTEMPTS = 2
COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT = 100
COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW = timedelta(minutes=15)
COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS = {
    "asian_handicap": {"home", "away"},
    "total_goals": {"over", "under"},
    "match_winner": {"home", "draw", "away"},
}
STANDARD_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH = 300
STANDARD_HISTORICAL_ODDS_TARGET_SNAPSHOTS_PER_MARKET_TYPE = 100
RAW_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH = 800
RAW_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MARKET_TYPE = 250

API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS = {
    "1": 16,
    "39": 17,
    "40": 18,
    "41": 24,
    "61": 34,
    "62": 182,
    "71": 325,
    "78": 35,
    "79": 44,
    "88": 37,
    "89": 131,
    "94": 238,
    "98": 196,
    "106": 202,
    "113": 40,
    "114": 46,
    "119": 39,
    "128": 155,
    "135": 23,
    "136": 53,
    "140": 8,
    "141": 54,
    "144": 38,
    "169": 649,
    "179": 36,
    "188": 136,
    "197": 185,
    "203": 52,
    "207": 215,
    "218": 45,
    "235": 203,
    "244": 41,
    "253": 242,
    "265": 27665,
    "283": 152,
    "292": 410,
    "293": 777,
    "307": 955,
    "103": 20,
    "104": 22,
    "120": 47,
    "164": 188,
    "262": 27466,
    "274": 1015,
    "357": 192,
    "358": 193,
    "1087": 55,
}


@dataclass(frozen=True)
class OddsPapiSyncPlan:
    candidate_match_count: int
    estimated_request_count: int
    skipped_existing_odds_count: int
    candidate_matches: tuple["OddsPapiPlanMatch", ...] = ()


@dataclass(frozen=True)
class OddsPapiPlanMatch:
    match_id: int
    league_name: str
    kickoff_time: datetime
    home_team_name: str
    away_team_name: str
    estimated_request_count: int


@dataclass(frozen=True)
class OddsPapiSyncResult:
    processed_match_count: int
    matched_count: int
    failed_match_count: int
    inserted_snapshot_count: int
    skipped_duplicate_snapshot_count: int
    skipped_existing_odds_count: int
    asian_handicap_count: int
    total_goals_count: int
    requests_used: int
    match_winner_count: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class OddsPapiProbeReport:
    probed_match_count: int
    available_match_count: int
    failed_match_count: int
    skipped_existing_odds_count: int
    requests_used: int
    matches: tuple["OddsPapiProbeMatch", ...] = ()


@dataclass(frozen=True)
class OddsPapiProbeMatch:
    match_id: int
    league_name: str
    kickoff_time: datetime
    home_team_name: str
    away_team_name: str
    available: bool
    source_fixture_id: str | None
    outcome_count: int
    reason: str


@dataclass(frozen=True)
class HistoricalOddsStoreSummary:
    inserted_count: int
    skipped_duplicate_count: int
    asian_handicap_count: int
    total_goals_count: int
    match_winner_count: int = 0
    skipped_protected_count: int = 0


class OddsPapiRequestLimiter:
    def __init__(self, cooldown_seconds: float = 0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_request_at = 0.0
        self._lock = Lock()

    def set_cooldown(self, cooldown_seconds: float) -> None:
        with self._lock:
            self.cooldown_seconds = cooldown_seconds

    def wait(self) -> None:
        if self.cooldown_seconds <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if self._last_request_at > 0 and elapsed < self.cooldown_seconds:
                time.sleep(self.cooldown_seconds - elapsed)
            self._last_request_at = time.monotonic()


GLOBAL_HISTORICAL_ODDS_LIMITER = OddsPapiRequestLimiter()
GLOBAL_FIXTURE_LIMITER = OddsPapiRequestLimiter()
GLOBAL_MARKET_DEFINITIONS_CACHE: dict[tuple[int, str], list[dict[str, Any]]] = {}
GLOBAL_MARKET_DEFINITIONS_CACHE_LOCK = Lock()


class OddsPapiSyncClient:
    def __init__(
        self,
        client: OddsPapiClient,
        bookmaker: str = DEFAULT_BOOKMAKER,
        fixture_cooldown_seconds: float = 7.5,
        fixture_limiter: OddsPapiRequestLimiter | None = None,
        historical_odds_cooldown_seconds: float = 0,
        historical_odds_limiter: OddsPapiRequestLimiter | None = None,
        historical_odds_rate_limit_backoff_seconds: float = 30,
    ):
        self.client = client
        self.bookmaker = bookmaker.lower()
        self._last_fixture_request_at = 0.0
        self._last_historical_odds_request_at = 0.0
        self.fixture_cooldown_seconds = fixture_cooldown_seconds
        self.fixture_limiter = fixture_limiter
        self.historical_odds_cooldown_seconds = historical_odds_cooldown_seconds
        self.historical_odds_limiter = historical_odds_limiter
        self.historical_odds_rate_limit_backoff_seconds = historical_odds_rate_limit_backoff_seconds
        self._market_definitions_cache: list[dict[str, Any]] | None = None

    @property
    def request_count(self) -> int:
        return self.client.request_count

    def fetch_fixtures(
        self,
        tournament_id: int,
        kickoff_time: datetime,
        *,
        require_available_odds: bool = True,
    ) -> list[OddsPapiFixture]:
        self._respect_fixture_cooldown()
        start_time = _as_utc(kickoff_time) - timedelta(hours=2)
        end_time = _as_utc(kickoff_time) + timedelta(hours=2)
        params = {
            "sportId": SOCCER_SPORT_ID,
            "tournamentId": tournament_id,
            "from": _format_utc_time(start_time),
            "to": _format_utc_time(end_time),
        }
        if require_available_odds:
            params["statusId"] = 2
            params["hasOdds"] = True
        try:
            payload = self.client.get("fixtures", params)
        except OddsPapiApiError as exc:
            if exc.status_code != 404 or not require_available_odds:
                raise
            self._mark_fixture_request_finished()
            fallback_params = dict(params)
            fallback_params.pop("statusId", None)
            fallback_params.pop("hasOdds", None)
            self._respect_fixture_cooldown()
            payload = self.client.get("fixtures", fallback_params)
        finally:
            self._mark_fixture_request_finished()
        return [_map_fixture(item) for item in payload]

    def fetch_historical_odds(
        self,
        source_fixture_id: str,
        outcome_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "sportId": SOCCER_SPORT_ID,
            "fixtureId": source_fixture_id,
            "bookmakers": self.bookmaker,
        }
        if outcome_id is not None:
            params["outcomeId"] = outcome_id
        timeout_seconds = getattr(self.client, "timeout_seconds", None) or 20
        for attempt in range(1, HISTORICAL_ODDS_TIMEOUT_ATTEMPTS + 1):
            self._respect_historical_odds_cooldown()
            executor = ThreadPoolExecutor(max_workers=1)
            shut_down = False
            try:
                future = executor.submit(_HistoricalOddsRequest(self.client, params))
                return future.result(timeout=timeout_seconds)
            except FutureTimeoutError:
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                shut_down = True
                self.reset_session()
                self._last_historical_odds_request_at = time.monotonic()
                if attempt >= HISTORICAL_ODDS_TIMEOUT_ATTEMPTS:
                    raise OddsPapiApiError(
                        "OddsPapi historical-odds request timed out after "
                        f"{HISTORICAL_ODDS_TIMEOUT_ATTEMPTS} attempts"
                    ) from None
            finally:
                if not shut_down:
                    executor.shutdown(wait=True)
                self._last_historical_odds_request_at = time.monotonic()

        raise OddsPapiApiError("OddsPapi historical-odds request timed out")

    def reset_session(self) -> None:
        reset = getattr(self.client, "reset_session", None)
        if callable(reset):
            reset()

    def fetch_markets(self, source_fixture_id: str) -> list[dict[str, Any]]:
        if self._market_definitions_cache is not None:
            return self._market_definitions_cache
        cache_key = (SOCCER_SPORT_ID, self.bookmaker)
        with GLOBAL_MARKET_DEFINITIONS_CACHE_LOCK:
            cached_markets = GLOBAL_MARKET_DEFINITIONS_CACHE.get(cache_key)
        if cached_markets is not None:
            self._market_definitions_cache = cached_markets
            return cached_markets
        market_definitions = self.client.get(
            "markets",
            {
                "sportId": SOCCER_SPORT_ID,
                "fixtureId": source_fixture_id,
                "bookmakers": self.bookmaker,
            },
        )
        with GLOBAL_MARKET_DEFINITIONS_CACHE_LOCK:
            cached_markets = GLOBAL_MARKET_DEFINITIONS_CACHE.setdefault(
                cache_key,
                market_definitions,
            )
        self._market_definitions_cache = cached_markets
        return cached_markets

    def clear_market_definitions_cache(self) -> None:
        self._market_definitions_cache = None

    def has_market_definitions_cache(self) -> bool:
        if self._market_definitions_cache is not None:
            return True
        cache_key = (SOCCER_SPORT_ID, self.bookmaker)
        with GLOBAL_MARKET_DEFINITIONS_CACHE_LOCK:
            return cache_key in GLOBAL_MARKET_DEFINITIONS_CACHE

    def _respect_fixture_cooldown(self) -> None:
        if self.fixture_limiter is not None:
            self.fixture_limiter.wait()
            return
        elapsed = time.monotonic() - self._last_fixture_request_at
        cooldown = self.fixture_cooldown_seconds
        if self._last_fixture_request_at > 0 and elapsed < cooldown:
            time.sleep(cooldown - elapsed)

    def _mark_fixture_request_finished(self) -> None:
        if self.fixture_limiter is None:
            self._last_fixture_request_at = time.monotonic()

    def _respect_historical_odds_cooldown(self) -> None:
        if self.historical_odds_limiter is not None:
            self.historical_odds_limiter.wait()
            return
        elapsed = time.monotonic() - self._last_historical_odds_request_at
        cooldown = self.historical_odds_cooldown_seconds
        if self._last_historical_odds_request_at > 0 and elapsed < cooldown:
            time.sleep(cooldown - elapsed)

    def backoff_after_historical_odds_rate_limit(self) -> None:
        if self.historical_odds_rate_limit_backoff_seconds <= 0:
            return
        time.sleep(self.historical_odds_rate_limit_backoff_seconds)


class _HistoricalOddsRequest:
    def __init__(self, client: OddsPapiClient, params: dict[str, Any]) -> None:
        self.client = client
        self.params = params
        self.fixture_id = str(params.get("fixtureId") or "")

    def __call__(self) -> list[dict[str, Any]]:
        return self.client.get(
            "historical-odds",
            self.params,
        )


def build_oddspapi_sync_plan(
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
) -> str:
    with _open_session() as session:
        plan = build_oddspapi_sync_plan_for_session(
            session=session,
            season=season,
            max_matches=max_matches,
            league_ids=league_ids,
            from_date=from_date,
        )
    return format_oddspapi_sync_plan(plan)


def run_oddspapi_sync(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = STANDARD_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH,
    skip_match_ids: set[int] | None = None,
    match_ids: set[int] | None = None,
    league_ids: set[str] | None = None,
    from_date: datetime | None = None,
    historical_odds_cooldown_seconds: float = 6,
    refresh_pre_kickoff_existing: bool = False,
    bookmaker: str = DEFAULT_BOOKMAKER,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    settings = load_project_settings()
    GLOBAL_FIXTURE_LIMITER.set_cooldown(7.5)
    GLOBAL_HISTORICAL_ODDS_LIMITER.set_cooldown(historical_odds_cooldown_seconds)
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(
        raw_client,
        bookmaker=bookmaker,
        fixture_limiter=GLOBAL_FIXTURE_LIMITER,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        historical_odds_limiter=GLOBAL_HISTORICAL_ODDS_LIMITER,
    )
    with _open_session() as session:
        result = run_oddspapi_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            max_snapshots_per_match=max_snapshots_per_match,
            skip_match_ids=skip_match_ids,
            match_ids=match_ids,
            league_ids=league_ids,
            from_date=from_date,
            refresh_pre_kickoff_existing=refresh_pre_kickoff_existing,
            progress_callback=progress_callback,
        )
    return _format_result(result)


def run_oddspapi_sync_result(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = STANDARD_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH,
    skip_match_ids: set[int] | None = None,
    match_ids: set[int] | None = None,
    league_ids: set[str] | None = None,
    from_date: datetime | None = None,
    historical_odds_cooldown_seconds: float = 6,
    refresh_pre_kickoff_existing: bool = False,
    bookmaker: str = DEFAULT_BOOKMAKER,
    progress_callback: Callable[[str], None] | None = None,
) -> OddsPapiSyncResult:
    settings = load_project_settings()
    GLOBAL_FIXTURE_LIMITER.set_cooldown(7.5)
    GLOBAL_HISTORICAL_ODDS_LIMITER.set_cooldown(historical_odds_cooldown_seconds)
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(
        raw_client,
        bookmaker=bookmaker,
        fixture_limiter=GLOBAL_FIXTURE_LIMITER,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        historical_odds_limiter=GLOBAL_HISTORICAL_ODDS_LIMITER,
    )
    with _open_session() as session:
        return run_oddspapi_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            max_snapshots_per_match=max_snapshots_per_match,
            skip_match_ids=skip_match_ids,
            match_ids=match_ids,
            league_ids=league_ids,
            from_date=from_date,
            refresh_pre_kickoff_existing=refresh_pre_kickoff_existing,
            progress_callback=progress_callback,
        )


def build_oddspapi_probe_report(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    skip_match_ids: set[int] | None = None,
    bookmaker: str = DEFAULT_BOOKMAKER,
) -> str:
    settings = load_project_settings()
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(
        raw_client,
        bookmaker=bookmaker,
        historical_odds_cooldown_seconds=5,
    )
    with _open_session() as session:
        report = build_oddspapi_probe_report_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            skip_match_ids=skip_match_ids,
        )
    return format_oddspapi_probe_report(report)


def build_oddspapi_match_report(match_id: int) -> str:
    with _open_session() as session:
        return build_oddspapi_match_report_for_session(session, match_id)


def build_oddspapi_match_report_for_session(session: Session, match_id: int) -> str:
    match = session.query(Match).filter(Match.id == match_id).one_or_none()
    if match is None:
        return f"未找到比赛 id={match_id}"
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter_by(match_id=match_id, source_name=ODDSPAPI_SOURCE_NAME)
        .order_by(
            HistoricalOddsSnapshot.bookmaker,
            HistoricalOddsSnapshot.market_type,
            HistoricalOddsSnapshot.snapshot_time,
            HistoricalOddsSnapshot.market_line,
            HistoricalOddsSnapshot.outcome_side,
        )
        .all()
    )
    lines = [_format_match_brief(match), f"历史赔率快照 {len(snapshots)}"]
    for snapshot in snapshots:
        lines.append(
            f"{_format_beijing_time(snapshot.snapshot_time)} {snapshot.bookmaker} "
            f"{snapshot.market_type} line={snapshot.market_line} "
            f"{snapshot.outcome_side} odds={snapshot.odds}"
        )
    return "\n".join(lines)


def build_oddspapi_sync_plan_for_session(
    session: Session,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    from_date: datetime | None = None,
) -> OddsPapiSyncPlan:
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        from_date=from_date,
    )
    candidate_matches = tuple(_build_plan_match(session, match) for match in matches)
    estimated_request_count = sum(
        match.estimated_request_count for match in candidate_matches
    )
    return OddsPapiSyncPlan(
        candidate_match_count=len(matches),
        estimated_request_count=estimated_request_count,
        skipped_existing_odds_count=skipped_existing_odds,
        candidate_matches=candidate_matches,
    )


def _build_plan_match(session: Session, match: Match) -> OddsPapiPlanMatch:
    cached_source_match = _get_reusable_odds_source_match(session, match.id)
    return OddsPapiPlanMatch(
        match_id=match.id,
        league_name=match.league.name,
        kickoff_time=match.kickoff_time,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        estimated_request_count=2 if cached_source_match is not None else 3,
    )


def build_oddspapi_probe_report_for_session(
    session: Session,
    client: OddsPapiSyncClient,
    season: int,
    max_matches: int,
    skip_match_ids: set[int] | None = None,
) -> OddsPapiProbeReport:
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
    )
    if skip_match_ids:
        matches = [match for match in matches if match.id not in skip_match_ids]
    fixtures_by_tournament_id = {}
    probe_matches = []
    for match in matches:
        try:
            source_fixture_id = _resolve_source_fixture_id(
                session=session,
                client=client,
                match=match,
                fixtures_by_tournament_id=fixtures_by_tournament_id,
            )
            if source_fixture_id is None:
                probe_matches.append(_build_probe_match(match, False, None, 0, "未匹配到 OddsPapi 比赛"))
                continue
            market_definitions = client.fetch_markets(source_fixture_id)
            outcome_ids = _select_history_outcome_ids(market_definitions)
            if not outcome_ids:
                probe_matches.append(_build_probe_match(match, False, source_fixture_id, 0, "未找到亚盘/大小球 outcome"))
                continue
            probe_matches.append(
                _build_probe_match(match, True, source_fixture_id, len(outcome_ids), "可回填")
            )
        except OddsPapiApiError as exc:
            probe_matches.append(_build_probe_match(match, False, None, 0, str(exc)))
    available_count = len([item for item in probe_matches if item.available])
    failed_count = len(probe_matches) - available_count
    return OddsPapiProbeReport(
        probed_match_count=len(probe_matches),
        available_match_count=available_count,
        failed_match_count=failed_count,
        skipped_existing_odds_count=skipped_existing_odds,
        requests_used=client.request_count,
        matches=tuple(probe_matches),
    )


def run_oddspapi_sync_for_session(
    session: Session,
    client: OddsPapiSyncClient,
    season: int,
    max_matches: int,
    max_snapshots_per_match: int = STANDARD_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH,
    skip_match_ids: set[int] | None = None,
    match_ids: set[int] | None = None,
    league_ids: set[str] | None = None,
    from_date: datetime | None = None,
    refresh_pre_kickoff_existing: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> OddsPapiSyncResult:
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        from_date=from_date,
        match_ids=match_ids,
        refresh_pre_kickoff_existing=refresh_pre_kickoff_existing,
    )
    if skip_match_ids:
        matches = [match for match in matches if match.id not in skip_match_ids]
    fixtures_by_tournament_id = {}
    team_aliases = _load_team_aliases(session)
    matched = 0
    inserted = 0
    skipped_duplicates = 0
    asian_handicap_count = 0
    total_goals_count = 0
    match_winner_count = 0
    processed = 0
    failed = 0
    total = len(matches)
    for index, match in enumerate(matches, start=1):
        _emit_progress(progress_callback, _format_progress_start(index, total, match))
        try:
            tournament_id = API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS.get(
                str(match.league.source_league_id)
            )
            if tournament_id is None:
                _emit_progress(
                    progress_callback,
                    _format_progress_skip(index, total, match, "未配置 OddsPapi 联赛映射"),
                )
                continue
            cached_source_match = _get_reusable_odds_source_match(session, match.id)
            if cached_source_match is not None:
                source_fixture_id = cached_source_match.source_fixture_id
                matched += 1
                try:
                    store_summary = _fetch_and_store_historical_odds(
                        session=session,
                        client=client,
                        match=match,
                        source_fixture_id=source_fixture_id,
                        max_snapshots_per_match=max_snapshots_per_match,
                        progress_callback=progress_callback,
                    )
                except OddsPapiApiError as exc:
                    _mark_historical_odds_status(
                        session,
                        match.id,
                        _classify_historical_odds_error(exc),
                        str(exc),
                    )
                    raise
                _mark_historical_odds_status(
                    session,
                    match.id,
                    "success"
                    if store_summary.inserted_count > 0 or store_summary.skipped_protected_count > 0
                    else "empty",
                    None,
                )
                inserted += store_summary.inserted_count
                skipped_duplicates += store_summary.skipped_duplicate_count
                asian_handicap_count += store_summary.asian_handicap_count
                total_goals_count += store_summary.total_goals_count
                match_winner_count += store_summary.match_winner_count
                processed += 1
                _emit_progress(
                    progress_callback,
                    _format_progress_success(index, total, match, store_summary.inserted_count),
                )
                continue
            fixture_cache_key = _build_fixture_cache_key(tournament_id, match.kickoff_time)
            if fixture_cache_key not in fixtures_by_tournament_id:
                try:
                    _emit_progress(
                        progress_callback,
                        (
                            f"  fixture_lookup_start match_id={match.id} "
                            f"tournament_id={tournament_id}"
                        ),
                    )
                    started_at = time.monotonic()
                    fixtures_by_tournament_id[fixture_cache_key] = client.fetch_fixtures(
                        tournament_id=tournament_id,
                        kickoff_time=match.kickoff_time,
                    )
                    _emit_progress(
                        progress_callback,
                        (
                            f"  fixture_lookup_done match_id={match.id} "
                            f"fixtures={len(fixtures_by_tournament_id[fixture_cache_key])} "
                            f"elapsed={_format_elapsed_seconds(started_at)}"
                        ),
                    )
                except OddsPapiApiError as exc:
                    if _classify_historical_odds_error(exc) == "unavailable":
                        _store_unavailable_odds_source_match(session, match, str(exc))
                    else:
                        _store_fixture_lookup_failed_odds_source_match(session, match, str(exc))
                    raise
            _emit_progress(
                progress_callback,
                f"  fixture_match_start match_id={match.id} candidates={len(fixtures_by_tournament_id[fixture_cache_key])}",
            )
            candidate = find_best_odds_source_match(
                match=match,
                fixtures=fixtures_by_tournament_id[fixture_cache_key],
                api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
                team_aliases=team_aliases,
            )
            if candidate is None and fixtures_by_tournament_id[fixture_cache_key]:
                fallback_cache_key = (*fixture_cache_key, "unfiltered")
                if fallback_cache_key not in fixtures_by_tournament_id:
                    try:
                        _emit_progress(
                            progress_callback,
                            (
                                f"  fixture_lookup_unfiltered_start match_id={match.id} "
                                f"tournament_id={tournament_id}"
                            ),
                        )
                        started_at = time.monotonic()
                        fixtures_by_tournament_id[fallback_cache_key] = client.fetch_fixtures(
                            tournament_id=tournament_id,
                            kickoff_time=match.kickoff_time,
                            require_available_odds=False,
                        )
                        _emit_progress(
                            progress_callback,
                            (
                                f"  fixture_lookup_unfiltered_done match_id={match.id} "
                                f"fixtures={len(fixtures_by_tournament_id[fallback_cache_key])} "
                                f"elapsed={_format_elapsed_seconds(started_at)}"
                            ),
                        )
                    except OddsPapiApiError as exc:
                        if _classify_historical_odds_error(exc) == "unavailable":
                            _store_unavailable_odds_source_match(session, match, str(exc))
                        else:
                            _store_fixture_lookup_failed_odds_source_match(session, match, str(exc))
                        raise
                candidate = find_best_odds_source_match(
                    match=match,
                    fixtures=fixtures_by_tournament_id[fallback_cache_key],
                    api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
                    team_aliases=team_aliases,
                )
            if candidate is None:
                _store_unmatched_odds_source_match(session, match, "未匹配到 OddsPapi 比赛")
                _emit_progress(
                    progress_callback,
                    _format_progress_skip(index, total, match, "未匹配到 OddsPapi 比赛"),
                )
                continue
            _emit_progress(
                progress_callback,
                (
                    f"  fixture_match_done match_id={match.id} "
                    f"fixture={candidate.fixture.fixture_id} score={candidate.confidence}"
                ),
            )
            _store_odds_source_match(session, match, candidate)
            matched += 1
            try:
                store_summary = _fetch_and_store_historical_odds(
                    session=session,
                    client=client,
                    match=match,
                    source_fixture_id=candidate.fixture.fixture_id,
                    max_snapshots_per_match=max_snapshots_per_match,
                    progress_callback=progress_callback,
                )
            except OddsPapiApiError as exc:
                _mark_historical_odds_status(
                    session,
                    match.id,
                    _classify_historical_odds_error(exc),
                    str(exc),
                )
                raise
            _mark_historical_odds_status(
                session,
                match.id,
                "success"
                if store_summary.inserted_count > 0 or store_summary.skipped_protected_count > 0
                else "empty",
                None,
            )
            inserted += store_summary.inserted_count
            skipped_duplicates += store_summary.skipped_duplicate_count
            asian_handicap_count += store_summary.asian_handicap_count
            total_goals_count += store_summary.total_goals_count
            match_winner_count += store_summary.match_winner_count
            processed += 1
            _emit_progress(
                progress_callback,
                _format_progress_success(index, total, match, store_summary.inserted_count),
            )
        except OddsPapiApiError as exc:
            failed += 1
            _emit_progress(
                progress_callback,
                _format_progress_failure(index, total, match, str(exc)),
            )
        except OddsPapiRequestBudgetExceededError as exc:
            return OddsPapiSyncResult(
                processed_match_count=processed,
                matched_count=matched,
                failed_match_count=failed,
                inserted_snapshot_count=inserted,
                skipped_duplicate_snapshot_count=skipped_duplicates,
                skipped_existing_odds_count=skipped_existing_odds,
                asian_handicap_count=asian_handicap_count,
                total_goals_count=total_goals_count,
                match_winner_count=match_winner_count,
                requests_used=client.request_count,
                error_message=str(exc),
            )
    return OddsPapiSyncResult(
        processed_match_count=processed,
        matched_count=matched,
        failed_match_count=failed,
        inserted_snapshot_count=inserted,
        skipped_duplicate_snapshot_count=skipped_duplicates,
        skipped_existing_odds_count=skipped_existing_odds,
        asian_handicap_count=asian_handicap_count,
        total_goals_count=total_goals_count,
        match_winner_count=match_winner_count,
        requests_used=client.request_count,
        error_message=_format_error_summary(failed),
    )


def _resolve_source_fixture_id(
    session: Session,
    client: OddsPapiSyncClient,
    match: Match,
    fixtures_by_tournament_id: dict,
) -> str | None:
    cached_source_match = _get_reusable_odds_source_match(session, match.id)
    if cached_source_match is not None:
        return cached_source_match.source_fixture_id
    tournament_id = API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS.get(
        str(match.league.source_league_id)
    )
    if tournament_id is None:
        return None
    fixture_cache_key = _build_fixture_cache_key(tournament_id, match.kickoff_time)
    if fixture_cache_key not in fixtures_by_tournament_id:
        fixtures_by_tournament_id[fixture_cache_key] = client.fetch_fixtures(
            tournament_id=tournament_id,
            kickoff_time=match.kickoff_time,
        )
    candidate = find_best_odds_source_match(
        match=match,
        fixtures=fixtures_by_tournament_id[fixture_cache_key],
        api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
        team_aliases=_load_team_aliases(session),
    )
    if candidate is None:
        return None
    _store_odds_source_match(session, match, candidate)
    return candidate.fixture.fixture_id


def _load_team_aliases(session: Session) -> list[ExternalAliasInput]:
    db_aliases = [
        ExternalAliasInput(
            canonical_name=alias.canonical_name,
            alias_name=alias.alias_name,
        )
        for alias in list_external_aliases(
            session,
            source_name=ODDSPAPI_SOURCE_NAME,
            entity_type="team",
        )
    ]
    config_aliases = _load_configured_team_aliases()
    return list(dict.fromkeys([*config_aliases, *db_aliases]))


def _load_configured_team_aliases(config_path: Path = Path("config/external_aliases.yaml")) -> list[ExternalAliasInput]:
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    aliases = []
    for item in payload.get("aliases", []):
        if item.get("entity_type") != "team" or item.get("source_name") != ODDSPAPI_SOURCE_NAME:
            continue
        canonical_name = item.get("canonical_name")
        alias_name = item.get("alias_name")
        if not canonical_name or not alias_name:
            continue
        aliases.append(
            ExternalAliasInput(
                canonical_name=str(canonical_name),
                alias_name=str(alias_name),
            )
        )
    return aliases


def _build_fixture_cache_key(tournament_id: int, kickoff_time: datetime) -> tuple[int, str, str]:
    start_time = _as_utc(kickoff_time) - timedelta(hours=2)
    end_time = _as_utc(kickoff_time) + timedelta(hours=2)
    return (tournament_id, _format_utc_time(start_time), _format_utc_time(end_time))


def _build_probe_match(
    match: Match,
    available: bool,
    source_fixture_id: str | None,
    outcome_count: int,
    reason: str,
) -> OddsPapiProbeMatch:
    return OddsPapiProbeMatch(
        match_id=match.id,
        league_name=match.league.name,
        kickoff_time=match.kickoff_time,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        available=available,
        source_fixture_id=source_fixture_id,
        outcome_count=outcome_count,
        reason=reason,
    )


def _fetch_and_store_historical_odds(
    session: Session,
    client: OddsPapiSyncClient,
    match: Match,
    source_fixture_id: str,
    max_snapshots_per_match: int,
    progress_callback: Callable[[str], None] | None = None,
) -> HistoricalOddsStoreSummary:
    if client.has_market_definitions_cache():
        _emit_progress(progress_callback, f"  复用盘口定义缓存 fixture={source_fixture_id}")
    else:
        _emit_progress(progress_callback, f"  拉取盘口定义 fixture={source_fixture_id}")
    _emit_progress(progress_callback, f"  markets_request_start fixture={source_fixture_id}")
    market_started_at = time.monotonic()
    market_definitions = client.fetch_markets(source_fixture_id)
    _emit_progress(
        progress_callback,
        (
            f"  markets_request_done fixture={source_fixture_id} "
            f"markets={len(market_definitions)} elapsed={_format_elapsed_seconds(market_started_at)}"
        ),
    )
    _emit_progress(
        progress_callback,
        f"  拉取历史赔率 fixture={source_fixture_id} mode=full_raw_compact_neighbors",
    )
    try:
        _emit_progress(
            progress_callback,
            (
                f"  historical_odds_request_start fixture={source_fixture_id} "
                "mode=full_raw_compact_neighbors"
            ),
        )
        historical_started_at = time.monotonic()
        raw_odds = client.fetch_historical_odds(source_fixture_id)
        _emit_progress(
            progress_callback,
            (
                f"  historical_odds_request_done fixture={source_fixture_id} "
                f"elapsed={_format_elapsed_seconds(historical_started_at)}"
            ),
        )
    except OddsPapiApiError as exc:
        if _is_rate_limit_error(exc):
            _emit_progress(
                progress_callback,
                "  遇到 OddsPapi 429 限流，暂停后停止当前比赛",
            )
            client.backoff_after_historical_odds_rate_limit()
        raise
    raw_snapshots = map_historical_odds(
        raw_odds,
        match_id=match.id,
        source_fixture_id=source_fixture_id,
        selected_bookmakers={client.bookmaker},
        market_definitions=market_definitions,
    )
    raw_snapshot_count = len(raw_snapshots)
    snapshot_timeline_kickoff_time = match_snapshot_timeline_kickoff_time(match)
    main_snapshots = build_dynamic_main_market_snapshots(
        raw_snapshots,
        kickoff_time=snapshot_timeline_kickoff_time,
    )
    raw_summary_snapshots = build_dynamic_neighbor_market_snapshots(
        raw_snapshots,
        kickoff_time=snapshot_timeline_kickoff_time,
    )
    snapshots = main_snapshots
    existing_24h_snapshot_count = _historical_odds_snapshot_count(
        session,
        match.id,
        kickoff_time=snapshot_timeline_kickoff_time,
    )
    if len(main_snapshots) < existing_24h_snapshot_count:
        _emit_progress(
            progress_callback,
            (
                "  warn_fewer_main_snapshots_continue_for_execution_timepoints "
                f"match_id={match.id} "
                f"new_main={len(main_snapshots)} "
                f"existing_24h={existing_24h_snapshot_count} "
                f"raw={raw_snapshot_count} "
                f"raw_summary={len(raw_summary_snapshots)}"
            ),
        )
    _emit_progress(
        progress_callback,
        f"  写入历史赔率 match_id={match.id} raw={raw_snapshot_count} main={len(main_snapshots)} raw_summary={len(raw_summary_snapshots)}",
    )
    store_main_started_at = time.monotonic()
    store_result = store_historical_odds_snapshots(
        session,
        snapshots,
        max_snapshots_per_match=max_snapshots_per_match,
        kickoff_time=snapshot_timeline_kickoff_time,
        use_oddspapi_training_sampler=True,
        oddspapi_target_snapshots_per_market_type=(
            STANDARD_HISTORICAL_ODDS_TARGET_SNAPSHOTS_PER_MARKET_TYPE
        ),
        execution_timepoint_source_snapshots=main_snapshots,
    )
    _emit_progress(
        progress_callback,
        (
            f"  store_main_done match_id={match.id} "
            f"inserted={store_result.inserted_count} "
            f"skipped={store_result.skipped_duplicate_count} "
            f"elapsed={_format_elapsed_seconds(store_main_started_at)}"
        ),
    )
    store_raw_started_at = time.monotonic()
    store_historical_odds_raw_snapshots(
        session,
        raw_summary_snapshots,
        max_snapshots_per_match=max(
            max_snapshots_per_match,
            RAW_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MATCH,
        ),
        kickoff_time=snapshot_timeline_kickoff_time,
        max_snapshots_per_market_type=RAW_HISTORICAL_ODDS_MAX_SNAPSHOTS_PER_MARKET_TYPE,
    )
    _emit_progress(
        progress_callback,
        (
            f"  store_raw_done match_id={match.id} "
            f"snapshots={len(raw_summary_snapshots)} "
            f"elapsed={_format_elapsed_seconds(store_raw_started_at)}"
        ),
    )
    return HistoricalOddsStoreSummary(
        inserted_count=store_result.inserted_count,
        skipped_duplicate_count=store_result.skipped_duplicate_count,
        asian_handicap_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "asian_handicap"]
        ),
        total_goals_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "total_goals"]
        ),
        match_winner_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "match_winner"]
        ),
    )
    _emit_progress(
        progress_callback,
        f"  拉取历史赔率 fixture={source_fixture_id}",
    )
    raw_odds_payloads = []
    outcome_errors = []
    for outcome_id in _select_history_outcome_ids(market_definitions):
        try:
            raw_odds_payloads.append(
                client.fetch_historical_odds(
                    source_fixture_id,
                    outcome_id=outcome_id,
                )
            )
        except OddsPapiApiError as exc:
            outcome_errors.append(exc)
            _emit_progress(
                progress_callback,
                f"  跳过历史赔率 outcome={outcome_id} error={exc}",
            )
            if _is_rate_limit_error(exc):
                _emit_progress(
                    progress_callback,
                    "  遇到 OddsPapi 429 限流，暂停后停止当前比赛后续 outcome",
                )
                client.backoff_after_historical_odds_rate_limit()
                break
            continue
    if not raw_odds_payloads and outcome_errors:
        raise outcome_errors[-1]
    raw_odds = _merge_nested_historical_odds_payloads(
        raw_odds_payloads,
        source_fixture_id=source_fixture_id,
    )
    snapshots = map_historical_odds(
        raw_odds,
        match_id=match.id,
        source_fixture_id=source_fixture_id,
        selected_bookmakers={client.bookmaker},
        market_definitions=market_definitions,
    )
    snapshots = build_dynamic_main_market_snapshots(
        snapshots,
        kickoff_time=match_snapshot_timeline_kickoff_time(match),
    )
    if not snapshots and outcome_errors:
        raise outcome_errors[-1]
    _emit_progress(progress_callback, f"  写入历史赔率 match_id={match.id}")
    store_result = store_historical_odds_snapshots(
        session,
        snapshots,
        max_snapshots_per_match=max_snapshots_per_match,
        kickoff_time=match_snapshot_timeline_kickoff_time(match),
        use_oddspapi_training_sampler=True,
        oddspapi_target_snapshots_per_market_type=(
            STANDARD_HISTORICAL_ODDS_TARGET_SNAPSHOTS_PER_MARKET_TYPE
        ),
        execution_timepoint_source_snapshots=snapshots,
    )
    return HistoricalOddsStoreSummary(
        inserted_count=store_result.inserted_count,
        skipped_duplicate_count=store_result.skipped_duplicate_count,
        asian_handicap_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "asian_handicap"]
        ),
        total_goals_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "total_goals"]
        ),
        match_winner_count=len(
            [snapshot for snapshot in snapshots if snapshot.market_type == "match_winner"]
        ),
    )


def _merge_nested_historical_odds_payloads(
    payloads: list[dict[str, Any]],
    *,
    source_fixture_id: str,
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "fixtureId": source_fixture_id,
        "bookmakers": {},
    }
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for bookmaker, bookmaker_payload in (payload.get("bookmakers") or {}).items():
            merged_bookmaker = merged["bookmakers"].setdefault(str(bookmaker), {"markets": {}})
            merged_markets = merged_bookmaker.setdefault("markets", {})
            for market_id, market_payload in (bookmaker_payload.get("markets") or {}).items():
                merged_market = merged_markets.setdefault(str(market_id), {"outcomes": {}})
                merged_outcomes = merged_market.setdefault("outcomes", {})
                merged_outcomes.update(market_payload.get("outcomes") or {})
    return merged


def _select_history_outcome_ids(market_definitions: list[dict[str, Any]]) -> list[str]:
    selected = []
    markets_by_type = {}
    for market in map_markets(market_definitions):
        markets_by_type.setdefault(market.market_type, []).append(market)
    for market_type in ("asian_handicap", "total_goals", "match_winner"):
        markets = markets_by_type.get(market_type) or []
        if not markets:
            continue
        selected_markets = _select_history_markets(market_type, markets)
        for market in selected_markets:
            selected.extend(market.outcome_ids)
    return selected


def _select_history_markets(market_type: str, markets: list) -> list:
    ranked = sorted(markets, key=_market_definition_score)
    if market_type == "match_winner":
        return ranked[:1]
    selected = []
    seen_lines = set()
    for market in ranked:
        if market.line in seen_lines:
            continue
        selected.append(market)
        seen_lines.add(market.line)
        if len(selected) >= 5:
            break
    return selected


def _market_definition_score(market) -> tuple[Decimal, Decimal]:
    if market.market_type == "asian_handicap":
        line_gap = abs(market.line)
    else:
        line_gap = abs(market.line - Decimal("2.5"))
    return line_gap, abs(market.line)


def _open_session():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def select_oddspapi_candidate_matches(
    session: Session,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    from_date: datetime | None = None,
    match_ids: set[int] | None = None,
    refresh_pre_kickoff_existing: bool = False,
    reference_time: datetime | None = None,
) -> tuple[list[Match], int]:
    league_priorities = _load_league_priority_by_source_id()
    query = (
        session.query(Match)
        .filter(Match.season == season)
        .order_by(Match.kickoff_time.desc())
    )
    if not match_ids:
        query = (
            query.filter(Match.status == "finished")
            .filter(Match.home_score.isnot(None))
            .filter(Match.away_score.isnot(None))
        )
    if match_ids:
        query = query.filter(Match.id.in_(match_ids))
    if from_date is not None:
        if isinstance(from_date, date) and not isinstance(from_date, datetime):
            from_date = datetime.combine(from_date, datetime_time.min, tzinfo=ZoneInfo("Asia/Shanghai"))
        query = query.filter(Match.kickoff_time >= from_date)
    selected = []
    skipped_existing_odds = 0
    for match in query:
        if str(match.league.source_league_id) not in API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS:
            continue
        if league_ids is not None and str(match.league.source_league_id) not in league_ids:
            continue
        if not match_ids and _has_complete_historical_odds(
            session,
            match.id,
            match.kickoff_time,
            refresh_pre_kickoff_existing=refresh_pre_kickoff_existing,
            reference_time=reference_time,
        ):
            skipped_existing_odds += 1
            continue
        if not match_ids and _has_terminal_historical_odds_status(session, match.id):
            skipped_existing_odds += 1
            continue
        selected.append(match)
    selected = sorted(
        selected,
        key=lambda match: (
            -league_priorities.get(str(match.league.source_league_id), match.league.priority or 0),
            -int(match.kickoff_time.timestamp()),
        ),
    )
    return selected[:max_matches], skipped_existing_odds


def _load_league_priority_by_source_id() -> dict[str, int]:
    settings = load_project_settings()
    return {
        str(league.api_football_id): league.priority
        for league in settings.leagues
        if league.enabled
    }


def _has_historical_odds(session: Session, match_id: int) -> bool:
    return _historical_odds_snapshot_count(session, match_id) > 0


def _has_complete_historical_odds(
    session: Session,
    match_id: int,
    kickoff_time: datetime,
    *,
    refresh_pre_kickoff_existing: bool = False,
    reference_time: datetime | None = None,
) -> bool:
    kickoff_utc = _as_utc(kickoff_time)
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter_by(match_id=match_id, source_name=ODDSPAPI_SOURCE_NAME)
        .filter(HistoricalOddsSnapshot.snapshot_time >= kickoff_utc - timedelta(hours=24))
        .filter(HistoricalOddsSnapshot.snapshot_time <= kickoff_utc)
        .all()
    )
    if len(snapshots) < COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT:
        return False
    latest_snapshot_time = max(
        (_historical_snapshot_as_utc(snapshot.snapshot_time) for snapshot in snapshots),
        default=None,
    )
    reference = reference_time or now_beijing()
    reference_utc = _as_utc(reference)
    if (
        refresh_pre_kickoff_existing
        and reference_utc < kickoff_utc
        and latest_snapshot_time is not None
        and latest_snapshot_time < reference_utc
    ):
        return False
    close_window_start = kickoff_utc - COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW
    close_snapshots = [
        snapshot
        for snapshot in snapshots
        if close_window_start <= _historical_snapshot_as_utc(snapshot.snapshot_time) <= kickoff_utc
    ]
    if not close_snapshots:
        return False
    sides_by_market: dict[str, set[str]] = {}
    for snapshot in close_snapshots:
        sides_by_market.setdefault(snapshot.market_type, set()).add(snapshot.outcome_side)
    return all(
        required_sides.issubset(sides_by_market.get(market_type, set()))
        for market_type, required_sides in COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS.items()
    )


def _historical_odds_snapshot_count(
    session: Session,
    match_id: int,
    *,
    kickoff_time: datetime | None = None,
) -> int:
    query = session.query(func.count(HistoricalOddsSnapshot.id)).filter_by(
        match_id=match_id,
        source_name=ODDSPAPI_SOURCE_NAME,
    )
    if kickoff_time is not None:
        kickoff_utc = _as_utc(kickoff_time)
        query = query.filter(HistoricalOddsSnapshot.snapshot_time >= kickoff_utc - timedelta(hours=24))
        query = query.filter(HistoricalOddsSnapshot.snapshot_time <= kickoff_utc)
    return int(query.scalar() or 0)


def _historical_snapshot_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("UTC"))


def _get_odds_source_match(session: Session, match_id: int) -> OddsSourceMatch | None:
    return (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match_id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )


def _get_reusable_odds_source_match(session: Session, match_id: int) -> OddsSourceMatch | None:
    source_match = _get_odds_source_match(session, match_id)
    if source_match is not None and not source_match.source_fixture_id:
        return None
    return source_match


def _has_terminal_historical_odds_status(session: Session, match_id: int) -> bool:
    source_match = _get_odds_source_match(session, match_id)
    return (
        source_match is not None
        and source_match.historical_odds_status in TERMINAL_HISTORICAL_ODDS_STATUSES
    )


def _classify_historical_odds_error(error: OddsPapiApiError) -> str:
    if getattr(error, "status_code", None) == 404 or "status=404" in str(error):
        return "unavailable"
    return "failed"


def _is_rate_limit_error(error: OddsPapiApiError) -> bool:
    return getattr(error, "status_code", None) == 429 or "status=429" in str(error)


def _mark_historical_odds_status(
    session: Session,
    match_id: int,
    status: str,
    error: str | None,
) -> None:
    source_match = _get_odds_source_match(session, match_id)
    if source_match is None:
        return
    source_match.historical_odds_status = status
    source_match.historical_odds_checked_at = now_beijing()
    source_match.historical_odds_error = error
    session.commit()


def _store_odds_source_match(session: Session, match: Match, candidate) -> None:
    existing = (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )
    if existing is None:
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                source_fixture_id=candidate.fixture.fixture_id,
                matched_at=now_beijing(),
                match_confidence=candidate.confidence,
                match_reason=candidate.reason,
            )
        )
    else:
        existing.source_fixture_id = candidate.fixture.fixture_id
        existing.matched_at = now_beijing()
        existing.match_confidence = candidate.confidence
        existing.match_reason = candidate.reason
    session.commit()


def _store_unmatched_odds_source_match(session: Session, match: Match, reason: str) -> None:
    existing = (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )
    if existing is None:
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                source_fixture_id="",
                matched_at=now_beijing(),
                match_confidence=Decimal("0.0000"),
                match_reason=reason,
                historical_odds_status="unmatched",
                historical_odds_checked_at=now_beijing(),
                historical_odds_error=reason,
            )
        )
    else:
        existing.match_confidence = Decimal("0.0000")
        existing.match_reason = reason
        existing.historical_odds_status = "unmatched"
        existing.historical_odds_checked_at = now_beijing()
        existing.historical_odds_error = reason
    session.commit()


def _store_unavailable_odds_source_match(session: Session, match: Match, reason: str) -> None:
    existing = (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )
    if existing is None:
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                source_fixture_id="",
                matched_at=now_beijing(),
                match_confidence=Decimal("0.0000"),
                match_reason=reason,
                historical_odds_status="unavailable",
                historical_odds_checked_at=now_beijing(),
                historical_odds_error=reason,
            )
        )
    else:
        existing.match_confidence = Decimal("0.0000")
        existing.match_reason = reason
        existing.historical_odds_status = "unavailable"
        existing.historical_odds_checked_at = now_beijing()
        existing.historical_odds_error = reason
    session.commit()


def _store_fixture_lookup_failed_odds_source_match(session: Session, match: Match, reason: str) -> None:
    existing = (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match.id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )
    if existing is None:
        session.add(
            OddsSourceMatch(
                match_id=match.id,
                source_name=ODDSPAPI_SOURCE_NAME,
                source_fixture_id="",
                matched_at=now_beijing(),
                match_confidence=Decimal("0.0000"),
                match_reason=reason,
                historical_odds_status="fixture_lookup_failed",
                historical_odds_checked_at=now_beijing(),
                historical_odds_error=reason,
            )
        )
    else:
        existing.match_confidence = Decimal("0.0000")
        existing.match_reason = reason
        existing.historical_odds_status = "fixture_lookup_failed"
        existing.historical_odds_checked_at = now_beijing()
        existing.historical_odds_error = reason
    session.commit()


def _map_fixture(item: dict[str, Any]) -> OddsPapiFixture:
    return OddsPapiFixture(
        fixture_id=str(item["fixtureId"]),
        tournament_id=int(item["tournamentId"]),
        start_time=_parse_utc_datetime(item["startTime"]),
        home_team_name=_team_name(item.get("homeTeam") or item.get("participant1Name")),
        away_team_name=_team_name(item.get("awayTeam") or item.get("participant2Name")),
    )


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(ZoneInfo("UTC"))


def _format_beijing_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y-%m-%d %H:%M:%S 北京时间"
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return value.astimezone(ZoneInfo("UTC"))


def _format_utc_time(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def _team_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value or "")


def _emit_progress(
    progress_callback: Callable[[str], None] | None,
    message: str,
) -> None:
    if progress_callback is not None:
        progress_callback(message)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _format_progress_start(index: int, total: int, match: Match) -> str:
    return f"[{index}/{total}] 开始 {_format_match_brief(match)}"


def _format_progress_success(
    index: int,
    total: int,
    match: Match,
    inserted_count: int,
) -> str:
    return f"[{index}/{total}] 完成 {_format_match_brief(match)} 写入快照 {inserted_count}"


def _format_progress_skip(index: int, total: int, match: Match, reason: str) -> str:
    return f"[{index}/{total}] 跳过 {_format_match_brief(match)} {reason}"


def _format_progress_failure(index: int, total: int, match: Match, reason: str) -> str:
    return f"[{index}/{total}] 失败 {_format_match_brief(match)} {reason}"


def _format_match_brief(match: Match) -> str:
    kickoff = match.kickoff_time.strftime("%Y-%m-%d %H:%M")
    return (
        f"id={match.id} {match.league.name} {kickoff} "
        f"{match.home_team.canonical_name} vs {match.away_team.canonical_name}"
    )


def _format_error_summary(failed_match_count: int) -> str | None:
    if failed_match_count <= 0:
        return None
    return f"{failed_match_count} 场比赛失败，已跳过继续"


def format_oddspapi_sync_plan(plan: OddsPapiSyncPlan) -> str:
    lines = [
        f"候选比赛 {plan.candidate_match_count}",
        f"预计请求 {plan.estimated_request_count}",
        f"跳过已有赔率 {plan.skipped_existing_odds_count}",
    ]
    lines.extend(_format_plan_match(match) for match in plan.candidate_matches)
    return "\n".join(lines)


def format_oddspapi_probe_report(report: OddsPapiProbeReport) -> str:
    skip_ids = [
        str(match.match_id)
        for match in report.matches
        if not match.available
    ]
    lines = [
        f"探测比赛 {report.probed_match_count}",
        f"可回填 {report.available_match_count}",
        f"失败比赛 {report.failed_match_count}",
        f"跳过已有赔率 {report.skipped_existing_odds_count}",
        f"实际请求 {report.requests_used}",
        f"推荐跳过 {','.join(skip_ids) if skip_ids else '-'}",
    ]
    lines.extend(_format_probe_match(match) for match in report.matches)
    return "\n".join(lines)


def _format_probe_match(match: OddsPapiProbeMatch) -> str:
    kickoff = match.kickoff_time.strftime("%Y-%m-%d %H:%M")
    status = "可回填" if match.available else "跳过"
    fixture = match.source_fixture_id or "-"
    return (
        f"id={match.match_id} {status} {match.league_name} {kickoff} "
        f"{match.home_team_name} vs {match.away_team_name} "
        f"fixture={fixture} outcomes={match.outcome_count} {match.reason}"
    )


def _format_plan_match(match: OddsPapiPlanMatch) -> str:
    kickoff = match.kickoff_time.strftime("%Y-%m-%d %H:%M")
    return (
        f"id={match.match_id} {match.league_name} {kickoff} "
        f"{match.home_team_name} vs {match.away_team_name} "
        f"预计请求 {match.estimated_request_count}"
    )


def _format_result(result: OddsPapiSyncResult) -> str:
    return "\n".join(
        [
            f"处理比赛 {result.processed_match_count}",
            f"匹配成功 {result.matched_count}",
            f"失败比赛 {result.failed_match_count}",
            f"写入快照 {result.inserted_snapshot_count}",
            f"跳过重复快照 {result.skipped_duplicate_snapshot_count}",
            f"跳过已有赔率 {result.skipped_existing_odds_count}",
            f"亚盘样本 {result.asian_handicap_count}",
            f"大小球样本 {result.total_goals_count}",
            f"实际请求 {result.requests_used}",
            f"错误 {result.error_message or '-'}",
        ]
    )

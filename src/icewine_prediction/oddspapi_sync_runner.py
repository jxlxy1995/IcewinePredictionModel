from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.dynamic_main_market_service import build_dynamic_main_market_snapshots
from icewine_prediction.historical_odds_service import store_historical_odds_snapshots
from icewine_prediction.models import HistoricalOddsSnapshot, Match, OddsSourceMatch
from icewine_prediction.odds_source_match_service import (
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
SELECTED_BOOKMAKERS = "pinnacle,sbobet"

API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS = {
    "39": 17,
    "40": 18,
    "61": 172,
    "62": 182,
    "78": 35,
    "79": 44,
    "135": 23,
    "140": 8,
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


class OddsPapiSyncClient:
    def __init__(
        self,
        client: OddsPapiClient,
        historical_odds_cooldown_seconds: float = 0,
    ):
        self.client = client
        self._last_fixture_request_at = 0.0
        self._last_historical_odds_request_at = 0.0
        self.historical_odds_cooldown_seconds = historical_odds_cooldown_seconds

    @property
    def request_count(self) -> int:
        return self.client.request_count

    def fetch_fixtures(self, tournament_id: int, kickoff_time: datetime) -> list[OddsPapiFixture]:
        self._respect_fixture_cooldown()
        start_time = _as_utc(kickoff_time) - timedelta(hours=2)
        end_time = _as_utc(kickoff_time) + timedelta(hours=2)
        payload = self.client.get(
            "fixtures",
            {
                "sportId": SOCCER_SPORT_ID,
                "tournamentId": tournament_id,
                "from": _format_utc_time(start_time),
                "to": _format_utc_time(end_time),
                "statusId": 2,
                "hasOdds": True,
            },
        )
        self._last_fixture_request_at = time.monotonic()
        return [_map_fixture(item) for item in payload]

    def fetch_historical_odds(
        self,
        source_fixture_id: str,
        outcome_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._respect_historical_odds_cooldown()
        params = {
            "sportId": SOCCER_SPORT_ID,
            "fixtureId": source_fixture_id,
            "bookmakers": SELECTED_BOOKMAKERS,
        }
        if outcome_id is not None:
            params["outcomeId"] = outcome_id
        try:
            return self.client.get(
                "historical-odds",
                params,
            )
        finally:
            self._last_historical_odds_request_at = time.monotonic()

    def fetch_markets(self, source_fixture_id: str) -> list[dict[str, Any]]:
        return self.client.get(
            "markets",
            {
                "sportId": SOCCER_SPORT_ID,
                "fixtureId": source_fixture_id,
                "bookmakers": SELECTED_BOOKMAKERS,
            },
        )

    def _respect_fixture_cooldown(self) -> None:
        elapsed = time.monotonic() - self._last_fixture_request_at
        if self._last_fixture_request_at > 0 and elapsed < 2:
            time.sleep(2 - elapsed)

    def _respect_historical_odds_cooldown(self) -> None:
        elapsed = time.monotonic() - self._last_historical_odds_request_at
        cooldown = self.historical_odds_cooldown_seconds
        if self._last_historical_odds_request_at > 0 and elapsed < cooldown:
            time.sleep(cooldown - elapsed)


def build_oddspapi_sync_plan(season: int, max_matches: int) -> str:
    with _open_session() as session:
        plan = build_oddspapi_sync_plan_for_session(
            session=session,
            season=season,
            max_matches=max_matches,
        )
    return format_oddspapi_sync_plan(plan)


def run_oddspapi_sync(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    max_snapshots_per_match: int = 200,
    skip_match_ids: set[int] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    settings = load_project_settings()
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(raw_client, historical_odds_cooldown_seconds=5)
    with _open_session() as session:
        result = run_oddspapi_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            max_snapshots_per_match=max_snapshots_per_match,
            skip_match_ids=skip_match_ids,
            progress_callback=progress_callback,
        )
    return _format_result(result)


def build_oddspapi_probe_report(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    skip_match_ids: set[int] | None = None,
) -> str:
    settings = load_project_settings()
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(raw_client, historical_odds_cooldown_seconds=5)
    with _open_session() as session:
        report = build_oddspapi_probe_report_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            skip_match_ids=skip_match_ids,
        )
    return format_oddspapi_probe_report(report)


def build_oddspapi_sync_plan_for_session(
    session: Session,
    season: int,
    max_matches: int,
) -> OddsPapiSyncPlan:
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
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
    cached_source_match = _get_odds_source_match(session, match.id)
    return OddsPapiPlanMatch(
        match_id=match.id,
        league_name=match.league.name,
        kickoff_time=match.kickoff_time,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        estimated_request_count=5 if cached_source_match is not None else 6,
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
    max_snapshots_per_match: int = 200,
    skip_match_ids: set[int] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> OddsPapiSyncResult:
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
    )
    if skip_match_ids:
        matches = [match for match in matches if match.id not in skip_match_ids]
    fixtures_by_tournament_id = {}
    matched = 0
    inserted = 0
    skipped_duplicates = 0
    asian_handicap_count = 0
    total_goals_count = 0
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
            cached_source_match = _get_odds_source_match(session, match.id)
            if cached_source_match is not None:
                source_fixture_id = cached_source_match.source_fixture_id
                matched += 1
                store_summary = _fetch_and_store_historical_odds(
                    session=session,
                    client=client,
                    match=match,
                    source_fixture_id=source_fixture_id,
                    max_snapshots_per_match=max_snapshots_per_match,
                    progress_callback=progress_callback,
                )
                inserted += store_summary.inserted_count
                skipped_duplicates += store_summary.skipped_duplicate_count
                asian_handicap_count += store_summary.asian_handicap_count
                total_goals_count += store_summary.total_goals_count
                processed += 1
                _emit_progress(
                    progress_callback,
                    _format_progress_success(index, total, match, store_summary.inserted_count),
                )
                continue
            fixture_cache_key = (tournament_id, match.id)
            if fixture_cache_key not in fixtures_by_tournament_id:
                fixtures_by_tournament_id[fixture_cache_key] = client.fetch_fixtures(
                    tournament_id=tournament_id,
                    kickoff_time=match.kickoff_time,
                )
            candidate = find_best_odds_source_match(
                match=match,
                fixtures=fixtures_by_tournament_id[fixture_cache_key],
                api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
            )
            if candidate is None:
                _emit_progress(
                    progress_callback,
                    _format_progress_skip(index, total, match, "未匹配到 OddsPapi 比赛"),
                )
                continue
            _store_odds_source_match(session, match, candidate)
            matched += 1
            store_summary = _fetch_and_store_historical_odds(
                session=session,
                client=client,
                match=match,
                source_fixture_id=candidate.fixture.fixture_id,
                max_snapshots_per_match=max_snapshots_per_match,
                progress_callback=progress_callback,
            )
            inserted += store_summary.inserted_count
            skipped_duplicates += store_summary.skipped_duplicate_count
            asian_handicap_count += store_summary.asian_handicap_count
            total_goals_count += store_summary.total_goals_count
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
        requests_used=client.request_count,
        error_message=_format_error_summary(failed),
    )


def _resolve_source_fixture_id(
    session: Session,
    client: OddsPapiSyncClient,
    match: Match,
    fixtures_by_tournament_id: dict,
) -> str | None:
    cached_source_match = _get_odds_source_match(session, match.id)
    if cached_source_match is not None:
        return cached_source_match.source_fixture_id
    tournament_id = API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS.get(
        str(match.league.source_league_id)
    )
    if tournament_id is None:
        return None
    fixture_cache_key = (tournament_id, match.id)
    if fixture_cache_key not in fixtures_by_tournament_id:
        fixtures_by_tournament_id[fixture_cache_key] = client.fetch_fixtures(
            tournament_id=tournament_id,
            kickoff_time=match.kickoff_time,
        )
    candidate = find_best_odds_source_match(
        match=match,
        fixtures=fixtures_by_tournament_id[fixture_cache_key],
        api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
    )
    if candidate is None:
        return None
    _store_odds_source_match(session, match, candidate)
    return candidate.fixture.fixture_id


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
    _emit_progress(progress_callback, f"  拉取盘口定义 fixture={source_fixture_id}")
    market_definitions = client.fetch_markets(source_fixture_id)
    outcome_ids = _select_history_outcome_ids(market_definitions)
    raw_odds_payloads = []
    for outcome_id in outcome_ids:
        _emit_progress(
            progress_callback,
            f"  拉取历史赔率 fixture={source_fixture_id} outcome={outcome_id}",
        )
        try:
            raw_odds_payloads.append(client.fetch_historical_odds(source_fixture_id, outcome_id))
        except OddsPapiApiError as exc:
            _emit_progress(
                progress_callback,
                f"  跳过历史赔率 fixture={source_fixture_id} outcome={outcome_id} {exc}",
            )
    _emit_progress(progress_callback, f"  写入历史赔率 match_id={match.id}")
    snapshots = []
    for raw_odds in raw_odds_payloads:
        snapshots.extend(
            map_historical_odds(
                raw_odds,
                match_id=match.id,
                source_fixture_id=source_fixture_id,
                market_definitions=market_definitions,
            )
        )
    snapshots = build_dynamic_main_market_snapshots(
        snapshots,
        kickoff_time=match.kickoff_time,
    )
    store_result = store_historical_odds_snapshots(
        session,
        snapshots,
        max_snapshots_per_match=max_snapshots_per_match,
        kickoff_time=match.kickoff_time,
        max_snapshots_per_market_type=50,
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
    )


def _select_history_outcome_ids(market_definitions: list[dict[str, Any]]) -> list[str]:
    selected = []
    for market in map_markets(market_definitions):
        selected.extend(market.outcome_ids)
    return selected


def _open_session():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def select_oddspapi_candidate_matches(
    session: Session,
    season: int,
    max_matches: int,
) -> tuple[list[Match], int]:
    league_priorities = _load_league_priority_by_source_id()
    query = (
        session.query(Match)
        .filter(Match.season == season)
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .order_by(Match.kickoff_time.desc())
    )
    selected = []
    skipped_existing_odds = 0
    for match in query:
        if str(match.league.source_league_id) not in API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS:
            continue
        if _has_historical_odds(session, match.id):
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
    return (
        session.query(HistoricalOddsSnapshot)
        .filter_by(match_id=match_id, source_name=ODDSPAPI_SOURCE_NAME)
        .first()
        is not None
    )


def _get_odds_source_match(session: Session, match_id: int) -> OddsSourceMatch | None:
    return (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match_id, source_name=ODDSPAPI_SOURCE_NAME)
        .one_or_none()
    )


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

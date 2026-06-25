from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.execution_timepoint_service import select_execution_timepoint_pair
from icewine_prediction.historical_training_sample_service import _pair_market_snapshots
from icewine_prediction.models import (
    DataSyncRun,
    HistoricalOddsSnapshot,
    Match,
    OddsSnapshot,
    PaperRecommendationRecord,
    RecommendationRecord,
)
from icewine_prediction.oddspapi_sync_runner import (
    COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT,
    COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW,
    COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS,
    ODDSPAPI_SOURCE_NAME,
    _as_utc,
    _historical_snapshot_as_utc,
)
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    PINNACLE_SOURCE_PRIORITY,
    filter_priority_pinnacle_snapshots,
)

EXECUTION_TIMEPOINT_TARGETS = (60, 30, 25, 20, 15, 10)
EXECUTION_TIMEPOINT_MARKETS = (
    ("asian_handicap", "亚盘"),
    ("total_goals", "大小球"),
    ("match_winner", "胜平负"),
)


@dataclass(frozen=True)
class MatchListLeagueOption:
    name: str
    display_name: str


@dataclass(frozen=True)
class MatchListFilters:
    start_time: str
    end_time: str
    league_name: str | None
    status_filter: str
    odds_filter: str
    search: str | None


@dataclass(frozen=True)
class MatchOddsStatus:
    key: str
    label: str


@dataclass(frozen=True)
class MatchOddsStatusFacts:
    complete_historical_match_ids: set[int]
    latest_odds_time_by_match_id: dict[int, datetime]
    odds_match_ids: set[int]


@dataclass(frozen=True)
class MatchListFreshness:
    latest_fixtures_results_sync: str | None
    latest_odds_sync: str | None
    latest_kickoff_time: str | None
    latest_odds_snapshot_time: str | None


@dataclass(frozen=True)
class MatchOddsSummary:
    asian_handicap: str | None
    total_goals: str | None
    match_winner: str | None


@dataclass(frozen=True)
class MatchListRow:
    match_id: int
    kickoff_time: str
    league_name: str
    league_display_name: str
    home_team_name: str
    home_team_display_name: str
    home_team_logo_url: str | None
    away_team_name: str
    away_team_display_name: str
    away_team_logo_url: str | None
    status: str
    status_group: str
    home_score: int | None
    away_score: int | None
    has_odds: bool
    odds_status_key: str
    odds_status_label: str
    odds_summary: MatchOddsSummary


@dataclass(frozen=True)
class MatchListWorkspace:
    filters: MatchListFilters
    freshness: MatchListFreshness
    leagues: list[MatchListLeagueOption]
    total_matches: int
    matches: list[MatchListRow]


@dataclass(frozen=True)
class RecommendationSummary:
    count: int
    label: str


@dataclass(frozen=True)
class ExecutionTimepointCoverageCell:
    target_minutes: int
    label: str
    available: bool
    snapshot_time: str | None
    market_line: str | None


@dataclass(frozen=True)
class ExecutionTimepointCoverageRow:
    market_type: str
    market_label: str
    cells: list[ExecutionTimepointCoverageCell]


@dataclass(frozen=True)
class ExecutionTimepointCoverage:
    targets: list[str]
    rows: list[ExecutionTimepointCoverageRow]
    available_count: int
    total_count: int
    health_key: str
    health_label: str


@dataclass(frozen=True)
class MatchDetail:
    match_id: int
    kickoff_time: str
    league_name: str
    league_display_name: str
    home_team_name: str
    home_team_display_name: str
    home_team_logo_url: str | None
    away_team_name: str
    away_team_display_name: str
    away_team_logo_url: str | None
    status: str
    status_group: str
    home_score: int | None
    away_score: int | None
    has_odds: bool
    odds_status_key: str
    odds_status_label: str
    team_data_note: str
    odds_summary: MatchOddsSummary
    execution_timepoint_coverage: ExecutionTimepointCoverage
    paper_recommendation_summary: RecommendationSummary
    formal_recommendation_summary: RecommendationSummary


MATCH_ODDS_STATUS_NONE = MatchOddsStatus("none", "无赔率")
MATCH_ODDS_STATUS_EARLY = MatchOddsStatus("early", "早盘")
MATCH_ODDS_STATUS_NEAR = MatchOddsStatus("near", "近盘")
MATCH_ODDS_STATUS_CLOSE = MatchOddsStatus("close", "临盘")
MATCH_ODDS_STATUS_PENDING_FILL = MatchOddsStatus("pending_fill", "待回填")
MATCH_ODDS_STATUS_FILLED = MatchOddsStatus("filled", "已回填")
MATCH_ODDS_STATUS_BY_KEY = {
    status.key: status
    for status in (
        MATCH_ODDS_STATUS_NONE,
        MATCH_ODDS_STATUS_EARLY,
        MATCH_ODDS_STATUS_NEAR,
        MATCH_ODDS_STATUS_CLOSE,
        MATCH_ODDS_STATUS_PENDING_FILL,
        MATCH_ODDS_STATUS_FILLED,
    )
}
LEGACY_ODDS_FILTERS = {"all", "with_odds", "without_odds"}
EMPTY_ODDS_SUMMARY = MatchOddsSummary(asian_handicap=None, total_goals=None, match_winner=None)


def record_sync_run(
    session: Session,
    *,
    sync_type: str,
    started_at: datetime,
    finished_at: datetime | None,
    status: str,
    days: int,
    created_count: int,
    updated_count: int,
    skipped_count: int,
    requests_used: int,
    error_message: str | None = None,
) -> DataSyncRun:
    run = DataSyncRun(
        sync_type=sync_type,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        days=days,
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        requests_used=requests_used,
        error_message=error_message,
    )
    session.add(run)
    session.commit()
    return run


def build_match_list_workspace(
    session: Session,
    *,
    now: datetime,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    league_name: str | None = None,
    status_filter: str = "all",
    odds_filter: str = "all",
    search: str | None = None,
    limit: int = 200,
    display_name_service: DisplayNameService | None = None,
) -> MatchListWorkspace:
    display_name_service = display_name_service or DisplayNameService()
    selected_odds_statuses = _parse_odds_filter_statuses(odds_filter)
    start, end = _time_window(now, start_time=start_time, end_time=end_time)
    query = _match_list_filtered_query(
        session,
        start=start,
        end=end,
        league_name=league_name,
        odds_filter="all",
        search=search,
        odds_match_ids=set(),
    )
    raw_matches = query.all()
    matches = [
        match
        for match in raw_matches
        if status_filter == "all" or _display_status_group(match, now=now) == status_filter
    ]
    odds_status_facts = _odds_status_facts(session, matches) if matches else _empty_odds_status_facts()
    matches = _filter_matches_by_legacy_odds_filter(
        matches,
        odds_filter=odds_filter,
        odds_match_ids=odds_status_facts.odds_match_ids,
    )
    odds_status_by_match_id = _odds_statuses_by_match_id(matches, now=now, facts=odds_status_facts)
    matches = _filter_matches_by_odds_status(matches, selected_statuses=selected_odds_statuses, odds_status_by_match_id=odds_status_by_match_id)
    visible_matches = matches[:limit]
    odds_summary_by_match_id = _odds_summaries_by_match_id(session, [match.id for match in visible_matches])
    return MatchListWorkspace(
        filters=MatchListFilters(
            start_time=_format_local_beijing_datetime(start),
            end_time=_format_local_beijing_datetime(end),
            league_name=league_name,
            status_filter=status_filter,
            odds_filter=odds_filter,
            search=search,
        ),
        freshness=_freshness(session),
        leagues=_league_options(
            session,
            start=start,
            end=end,
            display_name_service=display_name_service,
        ),
        total_matches=len(matches),
        matches=[
            _match_row(
                session,
                match,
                now=now,
                has_odds=match.id in odds_status_facts.odds_match_ids,
                odds_status=odds_status_by_match_id.get(match.id, MATCH_ODDS_STATUS_NONE),
                odds_summary=odds_summary_by_match_id.get(match.id, EMPTY_ODDS_SUMMARY),
                display_name_service=display_name_service,
            )
            for match in visible_matches
        ],
    )


def select_match_list_sync_targets(
    session: Session,
    *,
    now: datetime,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    league_name: str | None = None,
    status_filter: str = "all",
    odds_filter: str = "all",
    search: str | None = None,
) -> list[Match]:
    selected_odds_statuses = _parse_odds_filter_statuses(odds_filter)
    start, end = _time_window(now, start_time=start_time, end_time=end_time)
    raw_matches = _match_list_filtered_query(
        session,
        start=start,
        end=end,
        league_name=league_name,
        odds_filter="all",
        search=search,
        odds_match_ids=set(),
    ).all()
    matches = [
        match
        for match in raw_matches
        if status_filter == "all" or _display_status_group(match, now=now) == status_filter
    ]
    odds_status_facts = _odds_status_facts(session, matches) if matches else _empty_odds_status_facts()
    matches = _filter_matches_by_legacy_odds_filter(
        matches,
        odds_filter=odds_filter,
        odds_match_ids=odds_status_facts.odds_match_ids,
    )
    odds_status_by_match_id = _odds_statuses_by_match_id(matches, now=now, facts=odds_status_facts)
    return _filter_matches_by_odds_status(matches, selected_statuses=selected_odds_statuses, odds_status_by_match_id=odds_status_by_match_id)


def build_match_detail(
    session: Session,
    *,
    match_id: int,
    display_name_service: DisplayNameService | None = None,
) -> MatchDetail | None:
    display_name_service = display_name_service or DisplayNameService()
    match = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.id == match_id)
        .one_or_none()
    )
    if match is None:
        return None
    odds_status_facts = _odds_status_facts(session, [match])
    row = _match_row(
        session,
        match,
        now=datetime.now(ZoneInfo(BEIJING_TIMEZONE)),
        has_odds=match.id in odds_status_facts.odds_match_ids,
        odds_status=_odds_status(match, facts=odds_status_facts),
        odds_summary=_odds_summary(session, match.id),
        display_name_service=display_name_service,
    )
    paper_count = (
        session.query(func.count(PaperRecommendationRecord.id))
        .filter(PaperRecommendationRecord.match_id == match.id)
        .scalar()
        or 0
    )
    formal_count = (
        session.query(func.count(RecommendationRecord.id))
        .filter(RecommendationRecord.match_id == match.id)
        .scalar()
        or 0
    )
    return MatchDetail(
        match_id=row.match_id,
        kickoff_time=row.kickoff_time,
        league_name=row.league_name,
        league_display_name=row.league_display_name,
        home_team_name=row.home_team_name,
        home_team_display_name=row.home_team_display_name,
        home_team_logo_url=row.home_team_logo_url,
        away_team_name=row.away_team_name,
        away_team_display_name=row.away_team_display_name,
        away_team_logo_url=row.away_team_logo_url,
        status=row.status,
        status_group=row.status_group,
        home_score=row.home_score,
        away_score=row.away_score,
        has_odds=row.has_odds,
        odds_status_key=row.odds_status_key,
        odds_status_label=row.odds_status_label,
        team_data_note="待接入",
        odds_summary=row.odds_summary,
        execution_timepoint_coverage=_execution_timepoint_coverage(session, match),
        paper_recommendation_summary=RecommendationSummary(
            count=paper_count,
            label=f"纸面推荐 {paper_count} 条" if paper_count else "暂无纸面推荐记录",
        ),
        formal_recommendation_summary=RecommendationSummary(
            count=formal_count,
            label=f"正式推荐 {formal_count} 条" if formal_count else "暂无正式推荐记录",
        ),
    )


def _execution_timepoint_coverage(
    session: Session,
    match: Match,
) -> ExecutionTimepointCoverage:
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match.id)
        .filter(HistoricalOddsSnapshot.source_name.in_(PINNACLE_SOURCE_PRIORITY))
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .order_by(HistoricalOddsSnapshot.snapshot_time.asc())
        .all()
    )
    snapshots = filter_priority_pinnacle_snapshots(snapshots)
    kickoff_time = _snapshot_timeline_kickoff_time(match)
    rows: list[ExecutionTimepointCoverageRow] = []
    available_count = 0
    for market_type, market_label in EXECUTION_TIMEPOINT_MARKETS:
        pairs = _pair_market_snapshots(
            [snapshot for snapshot in snapshots if snapshot.market_type == market_type],
            market_type=market_type,
        )
        cells = []
        for target in EXECUTION_TIMEPOINT_TARGETS:
            selected = select_execution_timepoint_pair(
                pairs,
                kickoff_time=kickoff_time,
                target_minutes_before_kickoff=target,
            )
            if selected is not None:
                available_count += 1
            cells.append(
                ExecutionTimepointCoverageCell(
                    target_minutes=target,
                    label=f"T-{target}",
                    available=selected is not None,
                    snapshot_time=(
                        _format_local_beijing_datetime(selected.snapshot_time)
                        if selected is not None
                        else None
                    ),
                    market_line=(
                        f"{selected.market_line:.2f}" if selected is not None else None
                    ),
                )
            )
        rows.append(
            ExecutionTimepointCoverageRow(
                market_type=market_type,
                market_label=market_label,
                cells=cells,
            )
        )
    total_count = len(EXECUTION_TIMEPOINT_TARGETS) * len(EXECUTION_TIMEPOINT_MARKETS)
    health_key, health_label = _execution_timepoint_health(available_count, total_count)
    return ExecutionTimepointCoverage(
        targets=[f"T-{target}" for target in EXECUTION_TIMEPOINT_TARGETS],
        rows=rows,
        available_count=available_count,
        total_count=total_count,
        health_key=health_key,
        health_label=health_label,
    )


def _execution_timepoint_health(available_count: int, total_count: int) -> tuple[str, str]:
    if available_count <= 0:
        return "none", "无覆盖"
    ratio = Decimal(available_count) / Decimal(total_count)
    if ratio >= Decimal("0.90"):
        return "high", "健康"
    if ratio >= Decimal("0.60"):
        return "medium", "可用"
    return "low", "偏低"


def _snapshot_timeline_kickoff_time(match: Match) -> datetime:
    if match.fixture_timestamp is not None:
        return datetime.fromtimestamp(match.fixture_timestamp, ZoneInfo("UTC"))
    if match.kickoff_time.tzinfo is None:
        return match.kickoff_time.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE)).astimezone(ZoneInfo("UTC"))
    return match.kickoff_time.astimezone(ZoneInfo("UTC"))


def _match_list_filtered_query(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    league_name: str | None,
    odds_filter: str,
    search: str | None,
    odds_match_ids: set[int],
):
    query = (
        session.query(Match)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .filter(Match.kickoff_time >= start)
        .filter(Match.kickoff_time <= end)
    )
    if league_name:
        query = query.filter(Match.league.has(name=league_name))
    if odds_filter == "with_odds":
        query = query.filter(Match.id.in_(odds_match_ids or [-1]))
    if odds_filter == "without_odds":
        query = query.filter(~Match.id.in_(odds_match_ids or [-1]))
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Match.home_team.has(Match.home_team.property.mapper.class_.canonical_name.ilike(pattern)),
                Match.away_team.has(Match.away_team.property.mapper.class_.canonical_name.ilike(pattern)),
            )
        )
    return query


def _match_row(
    session: Session,
    match: Match,
    *,
    now: datetime,
    has_odds: bool,
    odds_status: MatchOddsStatus,
    odds_summary: MatchOddsSummary,
    display_name_service: DisplayNameService,
) -> MatchListRow:
    display_status = _display_status(match, now=now)
    return MatchListRow(
        match_id=match.id,
        kickoff_time=_format_local_beijing_datetime(match.kickoff_time),
        league_name=match.league.name,
        league_display_name=display_name_service.display_league(match.league.name),
        home_team_name=match.home_team.canonical_name,
        home_team_display_name=display_name_service.display_team(match.home_team.canonical_name),
        home_team_logo_url=match.home_team.logo_url,
        away_team_name=match.away_team.canonical_name,
        away_team_display_name=display_name_service.display_team(match.away_team.canonical_name),
        away_team_logo_url=match.away_team.logo_url,
        status=display_status,
        status_group=_status_group(display_status),
        home_score=match.home_score,
        away_score=match.away_score,
        has_odds=has_odds,
        odds_status_key=odds_status.key,
        odds_status_label=odds_status.label,
        odds_summary=odds_summary,
    )


def _freshness(session: Session) -> MatchListFreshness:
    latest_fixture_run = _latest_success_run(session, "fixtures_results")
    latest_odds_run = _latest_success_run(session, "odds")
    latest_kickoff = session.query(func.max(Match.kickoff_time)).scalar()
    latest_odds_snapshot = session.query(func.max(HistoricalOddsSnapshot.snapshot_time)).scalar()
    return MatchListFreshness(
        latest_fixtures_results_sync=_format_local_beijing_datetime(latest_fixture_run.finished_at)
        if latest_fixture_run and latest_fixture_run.finished_at
        else None,
        latest_odds_sync=_format_local_beijing_datetime(latest_odds_run.finished_at)
        if latest_odds_run and latest_odds_run.finished_at
        else None,
        latest_kickoff_time=_format_local_beijing_datetime(latest_kickoff) if latest_kickoff else None,
        latest_odds_snapshot_time=_format_utc_beijing_datetime(latest_odds_snapshot)
        if latest_odds_snapshot
        else None,
    )


def _latest_success_run(session: Session, sync_type: str) -> DataSyncRun | None:
    return (
        session.query(DataSyncRun)
        .filter(DataSyncRun.sync_type == sync_type)
        .filter(DataSyncRun.status == "success")
        .order_by(DataSyncRun.finished_at.desc(), DataSyncRun.id.desc())
        .first()
    )


def _league_options(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    display_name_service: DisplayNameService,
) -> list[MatchListLeagueOption]:
    rows = (
        session.query(Match)
        .options(joinedload(Match.league))
        .filter(Match.kickoff_time >= start)
        .filter(Match.kickoff_time <= end)
        .all()
    )
    return [
        MatchListLeagueOption(
            name=league_name,
            display_name=display_name_service.display_league(league_name),
        )
        for league_name in sorted({match.league.name for match in rows})
    ]


def _odds_match_ids(session: Session) -> set[int]:
    historical_rows = session.query(HistoricalOddsSnapshot.match_id).distinct().all()
    live_rows = session.query(OddsSnapshot.match_id).distinct().all()
    return {match_id for (match_id,) in historical_rows + live_rows}


def _empty_odds_status_facts() -> MatchOddsStatusFacts:
    return MatchOddsStatusFacts(
        complete_historical_match_ids=set(),
        latest_odds_time_by_match_id={},
        odds_match_ids=set(),
    )


def _odds_status_facts(session: Session, matches: list[Match]) -> MatchOddsStatusFacts:
    match_ids = [match.id for match in matches]
    if not match_ids:
        return _empty_odds_status_facts()
    live_latest = dict(
        session.query(OddsSnapshot.match_id, func.max(OddsSnapshot.captured_at))
        .filter(OddsSnapshot.match_id.in_(match_ids))
        .group_by(OddsSnapshot.match_id)
        .all()
    )
    historical_latest = dict(
        session.query(HistoricalOddsSnapshot.match_id, func.max(HistoricalOddsSnapshot.snapshot_time))
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .group_by(HistoricalOddsSnapshot.match_id)
        .all()
    )
    latest_odds_time_by_match_id = {
        match_id: max(times, key=_as_beijing_datetime)
        for match_id in set(live_latest) | set(historical_latest)
        if (times := [value for value in (live_latest.get(match_id), historical_latest.get(match_id)) if value is not None])
    }
    return MatchOddsStatusFacts(
        complete_historical_match_ids=_complete_historical_odds_match_ids(session, matches),
        latest_odds_time_by_match_id=latest_odds_time_by_match_id,
        odds_match_ids=set(live_latest) | set(historical_latest),
    )


def _complete_historical_odds_match_ids(session: Session, matches: list[Match]) -> set[int]:
    match_by_id = {match.id: match for match in matches}
    match_ids = list(match_by_id)
    if not match_ids:
        return set()
    earliest_kickoff_utc = min(_as_utc(match.kickoff_time) for match in matches)
    latest_kickoff_utc = max(_as_utc(match.kickoff_time) for match in matches)
    rows = (
        session.query(
            HistoricalOddsSnapshot.match_id,
            HistoricalOddsSnapshot.market_type,
            HistoricalOddsSnapshot.outcome_side,
            HistoricalOddsSnapshot.snapshot_time,
        )
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .filter(HistoricalOddsSnapshot.source_name.in_(PINNACLE_SOURCE_PRIORITY))
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .filter(HistoricalOddsSnapshot.snapshot_time >= earliest_kickoff_utc - timedelta(hours=24))
        .filter(HistoricalOddsSnapshot.snapshot_time <= latest_kickoff_utc)
        .all()
    )
    snapshots_by_match_id: dict[int, list[tuple[str, str, datetime]]] = {}
    for match_id, market_type, outcome_side, snapshot_time in rows:
        snapshots_by_match_id.setdefault(match_id, []).append((market_type, outcome_side, snapshot_time))
    complete_match_ids: set[int] = set()
    for match in matches:
        kickoff_utc = _as_utc(match.kickoff_time)
        snapshots = [
            snapshot
            for snapshot in snapshots_by_match_id.get(match.id, [])
            if kickoff_utc - timedelta(hours=24) <= _historical_snapshot_as_utc(snapshot[2]) <= kickoff_utc
        ]
        if len(snapshots) < COMPLETE_HISTORICAL_ODDS_24H_SNAPSHOT_COUNT:
            continue
        close_window_start = kickoff_utc - COMPLETE_HISTORICAL_ODDS_CLOSE_WINDOW
        sides_by_market: dict[str, set[str]] = {}
        for market_type, outcome_side, snapshot_time in snapshots:
            snapshot_utc = _historical_snapshot_as_utc(snapshot_time)
            if close_window_start <= snapshot_utc <= kickoff_utc:
                sides_by_market.setdefault(market_type, set()).add(outcome_side)
        if all(
            required_sides.issubset(sides_by_market.get(market_type, set()))
            for market_type, required_sides in COMPLETE_HISTORICAL_ODDS_REQUIRED_MARKETS.items()
        ):
            complete_match_ids.add(match.id)
    return complete_match_ids


def _filter_matches_by_legacy_odds_filter(
    matches: list[Match],
    *,
    odds_filter: str,
    odds_match_ids: set[int],
) -> list[Match]:
    legacy_filter = _legacy_odds_filter(odds_filter)
    if legacy_filter == "with_odds":
        return [match for match in matches if match.id in odds_match_ids]
    if legacy_filter == "without_odds":
        return [match for match in matches if match.id not in odds_match_ids]
    return matches


def _odds_statuses_by_match_id(
    matches: list[Match],
    *,
    now: datetime | None = None,
    facts: MatchOddsStatusFacts,
) -> dict[int, MatchOddsStatus]:
    return {
        match.id: _odds_status(match, now=now, facts=facts)
        for match in matches
    }


def _filter_matches_by_odds_status(
    matches: list[Match],
    *,
    selected_statuses: set[str],
    odds_status_by_match_id: dict[int, MatchOddsStatus],
) -> list[Match]:
    if not selected_statuses:
        return matches
    return [
        match
        for match in matches
        if odds_status_by_match_id.get(match.id, MATCH_ODDS_STATUS_NONE).key in selected_statuses
    ]


def _parse_odds_filter_statuses(odds_filter: str) -> set[str]:
    values = {value.strip() for value in odds_filter.split(",") if value.strip()}
    if not values or values & LEGACY_ODDS_FILTERS:
        return set()
    return {value for value in values if value in MATCH_ODDS_STATUS_BY_KEY}


def _legacy_odds_filter(odds_filter: str) -> str:
    return odds_filter if odds_filter in LEGACY_ODDS_FILTERS else "all"


def _odds_status(
    match: Match,
    *,
    now: datetime | None = None,
    facts: MatchOddsStatusFacts | None = None,
) -> MatchOddsStatus:
    facts = facts or _empty_odds_status_facts()
    status = _display_status(match, now=now) if now is not None else match.status
    status_group = _status_group(status)
    if status_group in {"finished", "live"}:
        if match.id in facts.complete_historical_match_ids:
            return MATCH_ODDS_STATUS_FILLED
        if match.id in facts.odds_match_ids:
            return MATCH_ODDS_STATUS_PENDING_FILL
        return MATCH_ODDS_STATUS_NONE

    latest_odds = facts.latest_odds_time_by_match_id.get(match.id)
    if latest_odds is None:
        return MATCH_ODDS_STATUS_NONE
    lead_time = _as_beijing_datetime(match.kickoff_time) - _as_beijing_datetime(latest_odds)
    if timedelta(0) <= lead_time <= timedelta(minutes=30):
        return MATCH_ODDS_STATUS_CLOSE
    if timedelta(minutes=30) < lead_time <= timedelta(hours=3):
        return MATCH_ODDS_STATUS_NEAR
    return MATCH_ODDS_STATUS_EARLY


def _odds_summary(session: Session, match_id: int) -> MatchOddsSummary:
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .order_by(HistoricalOddsSnapshot.snapshot_time.desc())
        .all()
    )
    return MatchOddsSummary(
        asian_handicap=_format_asian_handicap(_latest_market_pair(snapshots, "asian_handicap")),
        total_goals=_format_total_goals(_latest_market_pair(snapshots, "total_goals")),
        match_winner=_format_match_winner(snapshots),
    )


def _odds_summaries_by_match_id(
    session: Session,
    match_ids: list[int],
) -> dict[int, MatchOddsSummary]:
    if not match_ids:
        return {}
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .order_by(
            HistoricalOddsSnapshot.match_id.asc(),
            HistoricalOddsSnapshot.snapshot_time.desc(),
        )
        .all()
    )
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_match_id.setdefault(snapshot.match_id, []).append(snapshot)
    return {
        match_id: MatchOddsSummary(
            asian_handicap=_format_asian_handicap(_latest_market_pair(match_snapshots, "asian_handicap")),
            total_goals=_format_total_goals(_latest_market_pair(match_snapshots, "total_goals")),
            match_winner=_format_match_winner(match_snapshots),
        )
        for match_id, match_snapshots in snapshots_by_match_id.items()
    }


def _latest_market_pair(
    snapshots: list[HistoricalOddsSnapshot],
    market_type: str,
) -> tuple[Decimal, dict[str, Decimal]] | None:
    market_snapshots = [snapshot for snapshot in snapshots if snapshot.market_type == market_type]
    if not market_snapshots:
        return None
    latest_time = max(snapshot.snapshot_time for snapshot in market_snapshots)
    latest = [snapshot for snapshot in market_snapshots if snapshot.snapshot_time == latest_time]
    line = latest[0].market_line
    odds = {snapshot.outcome_side: snapshot.odds for snapshot in latest}
    return line, odds


def _format_asian_handicap(pair: tuple[Decimal, dict[str, Decimal]] | None) -> str | None:
    if pair is None:
        return None
    line, odds = pair
    if "away" in odds:
        return f"客队 {_format_signed_line(-line)} @ {_format_odds(odds['away'])}"
    if "home" in odds:
        return f"主队 {_format_signed_line(line)} @ {_format_odds(odds['home'])}"
    return None


def _format_total_goals(pair: tuple[Decimal, dict[str, Decimal]] | None) -> str | None:
    if pair is None:
        return None
    line, odds = pair
    if "over" in odds:
        return f"大 {line} @ {_format_odds(odds['over'])}"
    if "under" in odds:
        return f"小 {line} @ {_format_odds(odds['under'])}"
    return None


def _format_match_winner(snapshots: list[HistoricalOddsSnapshot]) -> str | None:
    pair = _latest_market_pair(snapshots, "match_winner")
    if pair is None:
        return None
    _, odds = pair
    if {"home", "draw", "away"}.issubset(odds):
        return (
            f"主 {_format_odds(odds['home'])} / "
            f"平 {_format_odds(odds['draw'])} / "
            f"客 {_format_odds(odds['away'])}"
        )
    return None


def _time_window(
    now: datetime,
    *,
    start_time: datetime | None,
    end_time: datetime | None,
) -> tuple[datetime, datetime]:
    local_now = _as_beijing_datetime(now)
    default_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    default_end = (default_start + timedelta(days=1)).replace(hour=12)
    return (
        _as_beijing_datetime(start_time) if start_time is not None else default_start,
        _as_beijing_datetime(end_time) if end_time is not None else default_end,
    )


def _display_status(match: Match, *, now: datetime) -> str:
    if (
        match.status in ("scheduled", "not_started", "1h", "2h", "ht", "live", "in_play", "halftime")
        and match.home_score is None
        and match.away_score is None
        and _as_beijing_datetime(match.kickoff_time) <= _as_beijing_datetime(now)
    ):
        return "pending_result"
    return match.status


def _display_status_group(match: Match, *, now: datetime) -> str:
    return _status_group(_display_status(match, now=now))


def _status_group(status: str) -> str:
    if status in ("scheduled", "not_started"):
        return "not_started"
    if status in ("pending_result", "live", "in_play", "halftime", "1h", "2h", "ht"):
        return "live"
    if status == "finished":
        return "finished"
    return status


def _format_local_beijing_datetime(value: datetime) -> str:
    return _as_beijing_datetime(value).isoformat()


def _as_beijing_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(BEIJING_TIMEZONE))
    return value.astimezone(ZoneInfo(BEIJING_TIMEZONE))


def _format_utc_beijing_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(BEIJING_TIMEZONE)).isoformat()


def _format_signed_line(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.00"))
    if quantized > 0:
        return f"+{quantized}"
    return str(quantized)


def _format_odds(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000")))

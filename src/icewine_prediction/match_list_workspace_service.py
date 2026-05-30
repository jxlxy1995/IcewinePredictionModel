from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.models import (
    DataSyncRun,
    HistoricalOddsSnapshot,
    Match,
    PaperRecommendationRecord,
    RecommendationRecord,
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
    team_data_note: str
    odds_summary: MatchOddsSummary
    paper_recommendation_summary: RecommendationSummary
    formal_recommendation_summary: RecommendationSummary


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
    odds_match_ids = _odds_match_ids(session)
    start, end = _time_window(now, start_time=start_time, end_time=end_time)
    query = _match_list_filtered_query(
        session,
        start=start,
        end=end,
        league_name=league_name,
        odds_filter=odds_filter,
        search=search,
        odds_match_ids=odds_match_ids,
    )
    raw_matches = query.all()
    matches = [
        match
        for match in raw_matches
        if status_filter == "all" or _display_status_group(match, now=now) == status_filter
    ]
    visible_matches = matches[:limit]
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
        leagues=_league_options(session, display_name_service=display_name_service),
        total_matches=len(matches),
        matches=[
            _match_row(
                session,
                match,
                now=now,
                has_odds=match.id in odds_match_ids,
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
    odds_match_ids = _odds_match_ids(session)
    start, end = _time_window(now, start_time=start_time, end_time=end_time)
    raw_matches = _match_list_filtered_query(
        session,
        start=start,
        end=end,
        league_name=league_name,
        odds_filter=odds_filter,
        search=search,
        odds_match_ids=odds_match_ids,
    ).all()
    matches = [
        match
        for match in raw_matches
        if status_filter == "all" or _display_status_group(match, now=now) == status_filter
    ]
    return matches


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
    row = _match_row(
        session,
        match,
        now=datetime.now(ZoneInfo(BEIJING_TIMEZONE)),
        has_odds=match.id in _odds_match_ids(session),
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
        team_data_note="待接入",
        odds_summary=row.odds_summary,
        paper_recommendation_summary=RecommendationSummary(
            count=paper_count,
            label=f"纸面推荐 {paper_count} 条" if paper_count else "暂无纸面推荐记录",
        ),
        formal_recommendation_summary=RecommendationSummary(
            count=formal_count,
            label=f"正式推荐 {formal_count} 条" if formal_count else "暂无正式推荐记录",
        ),
    )


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
        odds_summary=_odds_summary(session, match.id),
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
    display_name_service: DisplayNameService,
) -> list[MatchListLeagueOption]:
    rows = session.query(Match).options(joinedload(Match.league)).all()
    return [
        MatchListLeagueOption(
            name=league_name,
            display_name=display_name_service.display_league(league_name),
        )
        for league_name in sorted({match.league.name for match in rows})
    ]


def _odds_match_ids(session: Session) -> set[int]:
    rows = session.query(HistoricalOddsSnapshot.match_id).distinct().all()
    return {match_id for (match_id,) in rows}


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

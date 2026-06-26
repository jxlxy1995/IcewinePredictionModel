from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from icewine_prediction.dynamic_main_market_service import (
    build_dynamic_main_market_snapshots,
    build_dynamic_neighbor_market_snapshots,
)
from icewine_prediction.historical_odds_service import (
    DEFAULT_EXECUTION_SNAPSHOT_TARGETS,
    HistoricalOddsSnapshotInput,
    store_historical_odds_raw_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import (
    PINNACLE_BOOKMAKER,
    THE_ODDS_API_SOURCE_NAME,
)
from icewine_prediction.odds_source_match_service import normalize_team_name
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.the_odds_api_client import (
    TheOddsApiApiError,
    TheOddsApiClient,
    TheOddsApiRequestBudgetExceededError,
)
from icewine_prediction.sources.the_odds_api_odds_mapper import map_the_odds_api_event_odds
from icewine_prediction.time_utils import now_beijing


UTC = ZoneInfo("UTC")
DEFAULT_REGION = "eu"
DEFAULT_MARKETS = ("h2h", "spreads", "totals")
ALTERNATE_MARKETS = ("alternate_spreads", "alternate_totals")
API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS = {
    "1": "soccer_fifa_world_cup",
    "2": "soccer_uefa_champs_league",
    "3": "soccer_uefa_europa_league",
    "39": "soccer_epl",
    "40": "soccer_efl_champ",
    "41": "soccer_england_league1",
    "61": "soccer_france_ligue_one",
    "62": "soccer_france_ligue_two",
    "71": "soccer_brazil_campeonato",
    "78": "soccer_germany_bundesliga",
    "79": "soccer_germany_bundesliga2",
    "88": "soccer_netherlands_eredivisie",
    "94": "soccer_portugal_primeira_liga",
    "98": "soccer_japan_j_league",
    "103": "soccer_norway_eliteserien",
    "106": "soccer_poland_ekstraklasa",
    "113": "soccer_sweden_allsvenskan",
    "114": "soccer_sweden_superettan",
    "119": "soccer_denmark_superliga",
    "128": "soccer_argentina_primera_division",
    "135": "soccer_italy_serie_a",
    "136": "soccer_italy_serie_b",
    "140": "soccer_spain_la_liga",
    "141": "soccer_spain_segunda_division",
    "144": "soccer_belgium_first_div",
    "169": "soccer_china_superleague",
    "179": "soccer_spl",
    "197": "soccer_greece_super_league",
    "188": "soccer_australia_aleague",
    "203": "soccer_turkey_super_league",
    "207": "soccer_switzerland_superleague",
    "218": "soccer_austria_bundesliga",
    "235": "soccer_russia_premier_league",
    "244": "soccer_finland_veikkausliiga",
    "253": "soccer_usa_mls",
    "262": "soccer_mexico_ligamx",
    "265": "soccer_chile_campeonato",
    "292": "soccer_korea_kleague1",
    "307": "soccer_saudi_arabia_pro_league",
    "848": "soccer_uefa_europa_conference_league",
}


@dataclass(frozen=True)
class TheOddsApiPlanMatch:
    match_id: int
    league_name: str
    sport_key: str
    kickoff_time: datetime
    home_team_name: str
    away_team_name: str
    estimated_request_count: int


@dataclass(frozen=True)
class TheOddsApiSyncPlan:
    candidate_match_count: int
    estimated_request_count: int
    skipped_existing_odds_count: int
    candidate_matches: tuple[TheOddsApiPlanMatch, ...] = ()


@dataclass(frozen=True)
class TheOddsApiEventMatchCandidate:
    event_id: str
    event: dict[str, Any]
    confidence: Decimal
    reason: str


@dataclass(frozen=True)
class TheOddsApiSyncResult:
    processed_match_count: int
    matched_count: int
    failed_match_count: int
    inserted_snapshot_count: int
    skipped_duplicate_snapshot_count: int
    skipped_existing_odds_count: int
    asian_handicap_count: int
    total_goals_count: int
    match_winner_count: int
    requests_used: int
    error_message: str | None = None


class TheOddsApiSyncClient:
    def __init__(
        self,
        client: Any,
        *,
        bookmaker: str = PINNACLE_BOOKMAKER,
        region: str = DEFAULT_REGION,
        markets: tuple[str, ...] = DEFAULT_MARKETS,
    ) -> None:
        self.client = client
        self.bookmaker = bookmaker
        self.region = region
        self.markets = markets

    @property
    def request_count(self) -> int:
        return getattr(self.client, "request_count", 0)

    def fetch_current_odds(self, sport_key: str) -> list[dict[str, Any]]:
        payload = self.client.get(
            f"sports/{sport_key}/odds",
            {
                "regions": self.region,
                "bookmakers": self.bookmaker,
                "markets": ",".join(self.markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        return list(payload if isinstance(payload, list) else [])

    def fetch_historical_odds(self, sport_key: str, snapshot_time: datetime) -> list[dict[str, Any]]:
        payload = self.client.get(
            f"historical/sports/{sport_key}/odds",
            {
                "regions": self.region,
                "bookmakers": self.bookmaker,
                "markets": ",".join(self.markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "date": _format_the_odds_api_datetime(snapshot_time),
            },
        )
        if isinstance(payload, dict):
            data = payload.get("data")
            return list(data if isinstance(data, list) else [])
        return list(payload if isinstance(payload, list) else [])

    def fetch_event_odds(
        self,
        sport_key: str,
        event_id: str,
        *,
        markets: tuple[str, ...] = ALTERNATE_MARKETS,
    ) -> dict[str, Any]:
        payload = self.client.get(
            f"sports/{sport_key}/events/{event_id}/odds",
            {
                "regions": self.region,
                "bookmakers": self.bookmaker,
                "markets": ",".join(markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        return dict(payload if isinstance(payload, dict) else {})

    def fetch_historical_event_odds(
        self,
        sport_key: str,
        event_id: str,
        snapshot_time: datetime,
        *,
        markets: tuple[str, ...] = ALTERNATE_MARKETS,
    ) -> dict[str, Any]:
        payload = self.client.get(
            f"historical/sports/{sport_key}/events/{event_id}/odds",
            {
                "regions": self.region,
                "bookmakers": self.bookmaker,
                "markets": ",".join(markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "date": _format_the_odds_api_datetime(snapshot_time),
            },
        )
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return dict(payload["data"])
        return dict(payload if isinstance(payload, dict) else {})


def build_the_odds_api_sync_plan_for_session(
    *,
    session: Session,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
) -> TheOddsApiSyncPlan:
    matches, skipped = select_the_odds_api_candidate_matches(
        session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        match_ids=match_ids,
        from_date=from_date,
    )
    plan_matches = tuple(
        TheOddsApiPlanMatch(
            match_id=match.id,
            league_name=match.league.name,
            sport_key=API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS[str(match.league.source_league_id)],
            kickoff_time=match.kickoff_time,
            home_team_name=match.home_team.canonical_name,
            away_team_name=match.away_team.canonical_name,
            estimated_request_count=1,
        )
        for match in matches
    )
    return TheOddsApiSyncPlan(
        candidate_match_count=len(plan_matches),
        estimated_request_count=len({item.sport_key for item in plan_matches}),
        skipped_existing_odds_count=skipped,
        candidate_matches=plan_matches,
    )


def run_the_odds_api_sync_for_session(
    *,
    session: Session,
    client: TheOddsApiSyncClient,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
    now: datetime | None = None,
) -> TheOddsApiSyncResult:
    matches, skipped = select_the_odds_api_candidate_matches(
        session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        match_ids=match_ids,
        from_date=from_date,
        refresh_existing=refresh_existing,
    )
    events_by_sport_key: dict[str, list[dict[str, Any]]] = {}
    processed = matched = failed = inserted = skipped_duplicates = 0
    asian = totals = winners = 0
    error_message = None
    now_utc = _as_utc(now or now_beijing())
    for match in matches:
        sport_key = API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS[str(match.league.source_league_id)]
        try:
            if _as_utc(match.kickoff_time) <= now_utc:
                snapshots, raw_source_snapshots = _fetch_passed_kickoff_historical_snapshots(
                    client=client,
                    sport_key=sport_key,
                    match=match,
                )
                candidate = _historical_candidate_from_snapshots(match, snapshots)
            else:
                snapshots, raw_source_snapshots = _fetch_pre_kickoff_elapsed_historical_snapshots(
                    client=client,
                    sport_key=sport_key,
                    match=match,
                    now_utc=now_utc,
                )
                candidate = _historical_candidate_from_snapshots(match, snapshots)
                if candidate is None:
                    if sport_key not in events_by_sport_key:
                        events_by_sport_key[sport_key] = client.fetch_current_odds(sport_key)
                    events = events_by_sport_key[sport_key]
                    candidate = find_best_the_odds_api_event_match(match, events)
                    snapshots = (
                        map_the_odds_api_event_odds(
                            match_id=match.id,
                            event=candidate.event,
                            bookmaker=client.bookmaker,
                        )
                        if candidate is not None
                        else []
                    )
                    raw_source_snapshots = list(snapshots)
                    if candidate is not None:
                        raw_source_snapshots.extend(
                            _fetch_current_alternate_snapshots(
                                client=client,
                                sport_key=sport_key,
                                match=match,
                                event_id=candidate.event_id,
                            )
                        )
            if candidate is None:
                _store_source_match_status(
                    session,
                    match,
                    None,
                    "unmatched",
                    "no matching The Odds API event",
                )
                failed += 1
                continue
            if not snapshots:
                _store_source_match_status(session, match, candidate, "empty", "no Pinnacle markets")
                failed += 1
                continue
            main_snapshots = build_dynamic_main_market_snapshots(
                snapshots,
                kickoff_time=match.kickoff_time,
            )
            result = store_historical_odds_snapshots(
                session,
                main_snapshots,
                max_snapshots_per_match=400,
                kickoff_time=match.kickoff_time,
                execution_timepoint_source_snapshots=main_snapshots,
            )
            raw_summary_snapshots = build_dynamic_neighbor_market_snapshots(
                raw_source_snapshots,
                kickoff_time=match.kickoff_time,
            )
            store_historical_odds_raw_snapshots(
                session,
                raw_summary_snapshots,
                max_snapshots_per_match=800,
                kickoff_time=match.kickoff_time,
                max_snapshots_per_market_type=250,
            )
            _store_source_match_status(session, match, candidate, "success", None)
            matched += 1
            processed += 1
            inserted += result.inserted_count
            skipped_duplicates += result.skipped_duplicate_count
            asian += sum(1 for snapshot in snapshots if snapshot.market_type == "asian_handicap")
            totals += sum(1 for snapshot in snapshots if snapshot.market_type == "total_goals")
            winners += sum(1 for snapshot in snapshots if snapshot.market_type == "match_winner")
        except (TheOddsApiApiError, TheOddsApiRequestBudgetExceededError) as exc:
            error_message = str(exc)
            _store_source_match_status(session, match, None, "failed", error_message)
            failed += 1
            break
    return TheOddsApiSyncResult(
        processed_match_count=processed,
        matched_count=matched,
        failed_match_count=failed,
        inserted_snapshot_count=inserted,
        skipped_duplicate_snapshot_count=skipped_duplicates,
        skipped_existing_odds_count=skipped,
        asian_handicap_count=asian,
        total_goals_count=totals,
        match_winner_count=winners,
        requests_used=client.request_count,
        error_message=error_message,
    )


def find_best_the_odds_api_event_match(
    match: Match,
    events: list[dict[str, Any]],
    *,
    max_time_delta_seconds: int = 7200,
) -> TheOddsApiEventMatchCandidate | None:
    candidates = []
    kickoff = _as_utc(match.kickoff_time)
    for event in events:
        commence_time = _parse_time(event.get("commence_time"))
        if commence_time is None:
            continue
        time_delta = abs((kickoff - commence_time).total_seconds())
        if time_delta > max_time_delta_seconds:
            continue
        home_score = _team_similarity(match.home_team.canonical_name, str(event.get("home_team") or ""))
        away_score = _team_similarity(match.away_team.canonical_name, str(event.get("away_team") or ""))
        if home_score == Decimal("0") or away_score == Decimal("0"):
            continue
        candidates.append(
            TheOddsApiEventMatchCandidate(
                event_id=str(event.get("id") or ""),
                event=event,
                confidence=min(home_score, away_score),
                reason=f"sport/time/team match; time_delta_seconds={int(time_delta)}",
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)


def select_the_odds_api_candidate_matches(
    session: Session,
    *,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
) -> tuple[list[Match], int]:
    query = (
        session.query(Match)
        .join(League, Match.league_id == League.id)
        .options(joinedload(Match.league), joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(Match.season == season)
        .filter(Match.status.in_(("scheduled", "finished")))
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
    )
    if league_ids:
        query = query.filter(League.source_league_id.in_(league_ids))
    if match_ids:
        query = query.filter(Match.id.in_(match_ids))
    if from_date is not None:
        query = query.filter(Match.kickoff_time >= from_date)

    matches = []
    skipped = 0
    for match in query.all():
        if str(match.league.source_league_id) not in API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS:
            continue
        if not refresh_existing and _has_existing_snapshots(session, match.id):
            skipped += 1
            continue
        matches.append(match)
        if len(matches) >= max_matches:
            break
    return matches, skipped


def build_the_odds_api_sync_plan(
    *,
    season: int,
    max_matches: int,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
) -> str:
    with _open_session() as session:
        plan = build_the_odds_api_sync_plan_for_session(
            session=session,
            season=season,
            max_matches=max_matches,
            league_ids=league_ids,
            match_ids=match_ids,
            from_date=from_date,
        )
    return format_the_odds_api_sync_plan(plan)


def run_the_odds_api_sync(
    *,
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    league_ids: set[str] | None = None,
    match_ids: set[int] | None = None,
    from_date: datetime | None = None,
    refresh_existing: bool = False,
    bookmaker: str = PINNACLE_BOOKMAKER,
    region: str = DEFAULT_REGION,
) -> str:
    settings = load_project_settings()
    raw_client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = TheOddsApiSyncClient(raw_client, bookmaker=bookmaker, region=region)
    with _open_session() as session:
        result = run_the_odds_api_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            league_ids=league_ids,
            match_ids=match_ids,
            from_date=from_date,
            refresh_existing=refresh_existing,
        )
    return format_the_odds_api_sync_result(result)


def build_the_odds_api_match_report(match_id: int) -> str:
    with _open_session() as session:
        match = (
            session.query(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None:
            return f"match not found id={match_id}"
        snapshots = (
            session.query(HistoricalOddsSnapshot)
            .filter(HistoricalOddsSnapshot.match_id == match_id)
            .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
            .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
            .order_by(
                HistoricalOddsSnapshot.market_type,
                HistoricalOddsSnapshot.snapshot_time,
                HistoricalOddsSnapshot.market_line,
                HistoricalOddsSnapshot.outcome_side,
            )
            .all()
        )
        lines = [
            f"{match.id} {match.home_team.canonical_name} vs {match.away_team.canonical_name}",
            f"the_odds_api pinnacle snapshots={len(snapshots)}",
        ]
        for snapshot in snapshots:
            lines.append(
                f"{snapshot.snapshot_time.isoformat()} {snapshot.market_type} "
                f"line={snapshot.market_line} {snapshot.outcome_side} odds={snapshot.odds}"
            )
        return "\n".join(lines)


def format_the_odds_api_sync_plan(plan: TheOddsApiSyncPlan) -> str:
    lines = [
        "The Odds API Sync Plan",
        f"candidate_matches={plan.candidate_match_count}",
        f"estimated_requests={plan.estimated_request_count}",
        f"skipped_existing_odds={plan.skipped_existing_odds_count}",
    ]
    for item in plan.candidate_matches:
        lines.append(
            f"- match_id={item.match_id} sport={item.sport_key} "
            f"{item.home_team_name} vs {item.away_team_name} "
            f"kickoff={item.kickoff_time.isoformat()}"
        )
    return "\n".join(lines)


def format_the_odds_api_sync_result(result: TheOddsApiSyncResult) -> str:
    return "\n".join(
        [
            "The Odds API Sync Result",
            f"processed={result.processed_match_count}",
            f"matched={result.matched_count}",
            f"failed={result.failed_match_count}",
            f"inserted_snapshots={result.inserted_snapshot_count}",
            f"skipped_duplicates={result.skipped_duplicate_snapshot_count}",
            f"skipped_existing_odds={result.skipped_existing_odds_count}",
            f"asian_handicap={result.asian_handicap_count}",
            f"total_goals={result.total_goals_count}",
            f"match_winner={result.match_winner_count}",
            f"requests_used={result.requests_used}",
        ]
    )


def _has_existing_snapshots(session: Session, match_id: int) -> bool:
    return (
        session.query(HistoricalOddsSnapshot.id)
        .filter(HistoricalOddsSnapshot.match_id == match_id)
        .filter(HistoricalOddsSnapshot.source_name == THE_ODDS_API_SOURCE_NAME)
        .filter(HistoricalOddsSnapshot.bookmaker == PINNACLE_BOOKMAKER)
        .first()
        is not None
    )


def _store_source_match_status(
    session: Session,
    match: Match,
    candidate: TheOddsApiEventMatchCandidate | None,
    status: str,
    error: str | None,
) -> None:
    row = (
        session.query(OddsSourceMatch)
        .filter(OddsSourceMatch.match_id == match.id)
        .filter(OddsSourceMatch.source_name == THE_ODDS_API_SOURCE_NAME)
        .one_or_none()
    )
    if row is None:
        row = OddsSourceMatch(
            match_id=match.id,
            source_name=THE_ODDS_API_SOURCE_NAME,
            source_fixture_id=candidate.event_id if candidate is not None else f"unmatched-{match.id}",
            matched_at=now_beijing(),
            match_confidence=candidate.confidence if candidate is not None else Decimal("0.0000"),
            match_reason=candidate.reason if candidate is not None else status,
        )
        session.add(row)
    elif candidate is not None:
        row.source_fixture_id = candidate.event_id
        row.match_confidence = candidate.confidence
        row.match_reason = candidate.reason
    row.historical_odds_status = status
    row.historical_odds_checked_at = now_beijing()
    row.historical_odds_error = error
    session.commit()


def _team_similarity(left: str, right: str) -> Decimal:
    normalized_left = normalize_team_name(left)
    normalized_right = normalize_team_name(right)
    if normalized_left == normalized_right:
        return Decimal("1.0000")
    if normalized_left and normalized_right and (
        normalized_left in normalized_right or normalized_right in normalized_left
    ):
        return Decimal("0.9000")
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    if not left_tokens or not right_tokens:
        return Decimal("0")
    overlap = left_tokens & right_tokens
    if not overlap:
        return Decimal("0")
    return Decimal(len(overlap)) / Decimal(max(len(left_tokens), len(right_tokens)))


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return value.astimezone(UTC)


def _fetch_passed_kickoff_historical_snapshots(
    *,
    client: TheOddsApiSyncClient,
    sport_key: str,
    match: Match,
) -> tuple[list[HistoricalOddsSnapshotInput], list[HistoricalOddsSnapshotInput]]:
    return _fetch_historical_snapshots_at_times(
        client=client,
        sport_key=sport_key,
        match=match,
        snapshot_times=_standard_pre_kickoff_historical_snapshot_times(match.kickoff_time),
    )


def _fetch_historical_snapshots_at_times(
    *,
    client: TheOddsApiSyncClient,
    sport_key: str,
    match: Match,
    snapshot_times: tuple[datetime, ...],
) -> tuple[list[HistoricalOddsSnapshotInput], list[HistoricalOddsSnapshotInput]]:
    snapshots: list[HistoricalOddsSnapshotInput] = []
    raw_source_snapshots: list[HistoricalOddsSnapshotInput] = []
    seen_keys: set[tuple] = set()
    for snapshot_time in snapshot_times:
        events = client.fetch_historical_odds(sport_key, snapshot_time)
        candidate = find_best_the_odds_api_event_match(match, events)
        if candidate is None:
            continue
        for snapshot in map_the_odds_api_event_odds(
            match_id=match.id,
            event=candidate.event,
            bookmaker=client.bookmaker,
            snapshot_time_override=snapshot_time,
        ):
            raw_source_snapshots.append(snapshot)
            key = (
                snapshot.source_name,
                snapshot.bookmaker,
                snapshot.market_type,
                snapshot.market_id,
                snapshot.market_line,
                snapshot.outcome_side,
                _as_utc(snapshot.snapshot_time),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            snapshots.append(snapshot)
        raw_source_snapshots.extend(
            _fetch_historical_alternate_snapshots(
                client=client,
                sport_key=sport_key,
                match=match,
                event_id=candidate.event_id,
                snapshot_time=snapshot_time,
            )
        )
    return snapshots, raw_source_snapshots


def _fetch_pre_kickoff_elapsed_historical_snapshots(
    *,
    client: TheOddsApiSyncClient,
    sport_key: str,
    match: Match,
    now_utc: datetime,
) -> tuple[list[HistoricalOddsSnapshotInput], list[HistoricalOddsSnapshotInput]]:
    elapsed_snapshot_times = tuple(
        snapshot_time
        for snapshot_time in _standard_pre_kickoff_historical_snapshot_times(match.kickoff_time)
        if snapshot_time <= now_utc
    )
    if not elapsed_snapshot_times:
        return [], []
    return _fetch_historical_snapshots_at_times(
        client=client,
        sport_key=sport_key,
        match=match,
        snapshot_times=elapsed_snapshot_times,
    )


def _fetch_current_alternate_snapshots(
    *,
    client: TheOddsApiSyncClient,
    sport_key: str,
    match: Match,
    event_id: str,
) -> list[HistoricalOddsSnapshotInput]:
    try:
        event = client.fetch_event_odds(sport_key, event_id)
    except TheOddsApiApiError:
        return []
    return map_the_odds_api_event_odds(
        match_id=match.id,
        event=event,
        bookmaker=client.bookmaker,
    )


def _fetch_historical_alternate_snapshots(
    *,
    client: TheOddsApiSyncClient,
    sport_key: str,
    match: Match,
    event_id: str,
    snapshot_time: datetime,
) -> list[HistoricalOddsSnapshotInput]:
    try:
        event = client.fetch_historical_event_odds(sport_key, event_id, snapshot_time)
    except TheOddsApiApiError:
        return []
    return map_the_odds_api_event_odds(
        match_id=match.id,
        event=event,
        bookmaker=client.bookmaker,
        snapshot_time_override=snapshot_time,
    )


def _historical_candidate_from_snapshots(
    match: Match,
    snapshots: list[HistoricalOddsSnapshotInput],
) -> TheOddsApiEventMatchCandidate | None:
    if not snapshots:
        return None
    return TheOddsApiEventMatchCandidate(
        event_id=snapshots[0].source_fixture_id,
        event={},
        confidence=Decimal("1.0000"),
        reason="historical sport/time/team match; standard execution timepoints",
    )


def _standard_pre_kickoff_historical_snapshot_times(kickoff_time: datetime) -> tuple[datetime, ...]:
    kickoff_utc = _as_utc(kickoff_time)
    return tuple(
        kickoff_utc - timedelta(minutes=target)
        for target in DEFAULT_EXECUTION_SNAPSHOT_TARGETS
    )


def _format_the_odds_api_datetime(value: datetime) -> str:
    value = _as_utc(value)
    return value.isoformat().replace("+00:00", "Z")


def _open_session():
    from icewine_prediction.database import (
        create_database_engine,
        create_session_factory,
        initialize_database,
    )

    engine = create_database_engine()
    initialize_database(engine)
    return create_session_factory(engine)()

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.historical_odds_service import store_historical_odds_snapshots
from icewine_prediction.models import HistoricalOddsSnapshot, Match, OddsSourceMatch
from icewine_prediction.odds_source_match_service import (
    OddsPapiFixture,
    find_best_odds_source_match,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.oddspapi_client import OddsPapiClient
from icewine_prediction.sources.oddspapi_odds_mapper import map_historical_odds
from icewine_prediction.time_utils import now_beijing

ODDSPAPI_BASE_URL = "https://api.oddspapi.io/v4"
ODDSPAPI_SOURCE_NAME = "oddspapi"
SOCCER_SPORT_ID = 10
SELECTED_BOOKMAKERS = "pinnacle,bet365,sbobet"

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


@dataclass(frozen=True)
class OddsPapiSyncResult:
    processed_match_count: int
    matched_count: int
    inserted_snapshot_count: int
    skipped_duplicate_snapshot_count: int
    skipped_existing_odds_count: int
    asian_handicap_count: int
    total_goals_count: int
    requests_used: int


@dataclass(frozen=True)
class HistoricalOddsStoreSummary:
    inserted_count: int
    skipped_duplicate_count: int
    asian_handicap_count: int
    total_goals_count: int


class OddsPapiSyncClient:
    def __init__(self, client: OddsPapiClient):
        self.client = client

    @property
    def request_count(self) -> int:
        return self.client.request_count

    def fetch_fixtures(self, tournament_id: int) -> list[OddsPapiFixture]:
        payload = self.client.get(
            "fixtures",
            {
                "sportId": SOCCER_SPORT_ID,
                "tournamentId": tournament_id,
            },
        )
        return [_map_fixture(item) for item in payload]

    def fetch_historical_odds(self, source_fixture_id: str) -> list[dict[str, Any]]:
        return self.client.get(
            "historical-odds",
            {
                "sportId": SOCCER_SPORT_ID,
                "fixtureId": source_fixture_id,
                "bookmakers": SELECTED_BOOKMAKERS,
            },
        )


def build_oddspapi_sync_plan(season: int, max_matches: int) -> str:
    with _open_session() as session:
        plan = build_oddspapi_sync_plan_for_session(
            session=session,
            season=season,
            max_matches=max_matches,
        )
    return _format_plan(plan)


def run_oddspapi_sync(season: int, max_matches: int, request_budget: int) -> str:
    settings = load_project_settings()
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(raw_client)
    with _open_session() as session:
        result = run_oddspapi_sync_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
        )
    return _format_result(result)


def build_oddspapi_sync_plan_for_session(
    session: Session,
    season: int,
    max_matches: int,
) -> OddsPapiSyncPlan:
    matches, skipped_existing_odds = _select_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
    )
    tournament_ids = {
        API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS[str(match.league.source_league_id)]
        for match in matches
        if str(match.league.source_league_id) in API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS
    }
    estimated_request_count = len(tournament_ids) + len(matches)
    return OddsPapiSyncPlan(
        candidate_match_count=len(matches),
        estimated_request_count=estimated_request_count,
        skipped_existing_odds_count=skipped_existing_odds,
    )


def run_oddspapi_sync_for_session(
    session: Session,
    client: OddsPapiSyncClient,
    season: int,
    max_matches: int,
) -> OddsPapiSyncResult:
    matches, skipped_existing_odds = _select_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
    )
    fixtures_by_tournament_id = {}
    matched = 0
    inserted = 0
    skipped_duplicates = 0
    asian_handicap_count = 0
    total_goals_count = 0
    for match in matches:
        tournament_id = API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS.get(
            str(match.league.source_league_id)
        )
        if tournament_id is None:
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
            )
            inserted += store_summary.inserted_count
            skipped_duplicates += store_summary.skipped_duplicate_count
            asian_handicap_count += store_summary.asian_handicap_count
            total_goals_count += store_summary.total_goals_count
            continue
        if tournament_id not in fixtures_by_tournament_id:
            fixtures_by_tournament_id[tournament_id] = client.fetch_fixtures(tournament_id)
        candidate = find_best_odds_source_match(
            match=match,
            fixtures=fixtures_by_tournament_id[tournament_id],
            api_football_to_oddspapi_tournament_ids=API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
        )
        if candidate is None:
            continue
        _store_odds_source_match(session, match, candidate)
        matched += 1
        store_summary = _fetch_and_store_historical_odds(
            session=session,
            client=client,
            match=match,
            source_fixture_id=candidate.fixture.fixture_id,
        )
        inserted += store_summary.inserted_count
        skipped_duplicates += store_summary.skipped_duplicate_count
        asian_handicap_count += store_summary.asian_handicap_count
        total_goals_count += store_summary.total_goals_count
    return OddsPapiSyncResult(
        processed_match_count=len(matches),
        matched_count=matched,
        inserted_snapshot_count=inserted,
        skipped_duplicate_snapshot_count=skipped_duplicates,
        skipped_existing_odds_count=skipped_existing_odds,
        asian_handicap_count=asian_handicap_count,
        total_goals_count=total_goals_count,
        requests_used=client.request_count,
    )


def _fetch_and_store_historical_odds(
    session: Session,
    client: OddsPapiSyncClient,
    match: Match,
    source_fixture_id: str,
) -> HistoricalOddsStoreSummary:
    raw_odds = client.fetch_historical_odds(source_fixture_id)
    snapshots = map_historical_odds(
        raw_odds,
        match_id=match.id,
        source_fixture_id=source_fixture_id,
    )
    store_result = store_historical_odds_snapshots(session, snapshots)
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


def _open_session():
    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def _select_candidate_matches(
    session: Session,
    season: int,
    max_matches: int,
) -> tuple[list[Match], int]:
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
        if len(selected) >= max_matches:
            break
    return selected, skipped_existing_odds


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
        home_team_name=_team_name(item.get("homeTeam")),
        away_team_name=_team_name(item.get("awayTeam")),
    )


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(ZoneInfo("UTC"))


def _team_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value or "")


def _format_plan(plan: OddsPapiSyncPlan) -> str:
    return "\n".join(
        [
            f"候选比赛 {plan.candidate_match_count}",
            f"预计请求 {plan.estimated_request_count}",
            f"跳过已有赔率 {plan.skipped_existing_odds_count}",
        ]
    )


def _format_result(result: OddsPapiSyncResult) -> str:
    return "\n".join(
        [
            f"处理比赛 {result.processed_match_count}",
            f"匹配成功 {result.matched_count}",
            f"写入快照 {result.inserted_snapshot_count}",
            f"跳过重复快照 {result.skipped_duplicate_snapshot_count}",
            f"跳过已有赔率 {result.skipped_existing_odds_count}",
            f"亚盘样本 {result.asian_handicap_count}",
            f"大小球样本 {result.total_goals_count}",
            f"实际请求 {result.requests_used}",
        ]
    )

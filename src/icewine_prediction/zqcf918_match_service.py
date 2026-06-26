from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.display_service import DisplayNameService, DisplayNames
from icewine_prediction.models import Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import (
    ZQCF918_BASE_URL,
    ZQCF918_PINNACLE_COMPANY_ID,
    ZQCF918Client,
)


UTC = ZoneInfo("UTC")
BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ZQCF918MatchIdUpdate:
    match_id: int
    source_fixture_id: str
    reason: str
    confidence: Decimal = Decimal("1.0000")


def zqcf918_match_url(source_fixture_id: str) -> str:
    return (
        f"{ZQCF918_BASE_URL}/zsDetail"
        f"?matchId={source_fixture_id}&companyId={ZQCF918_PINNACLE_COMPANY_ID}&type=0"
    )


def get_zqcf918_match_id(session: Session, match_id: int) -> OddsSourceMatch | None:
    return (
        session.query(OddsSourceMatch)
        .filter_by(match_id=match_id, source_name=ZQCF918_SOURCE_NAME)
        .one_or_none()
    )


def upsert_zqcf918_match_id(session: Session, update: ZQCF918MatchIdUpdate) -> OddsSourceMatch:
    if session.get(Match, update.match_id) is None:
        raise ValueError("match not found")
    source_fixture_id = str(update.source_fixture_id).strip()
    if not source_fixture_id.isdigit():
        raise ValueError("zqcf918 match ID must be numeric")
    row = get_zqcf918_match_id(session, update.match_id)
    if row is None:
        row = OddsSourceMatch(
            match_id=update.match_id,
            source_name=ZQCF918_SOURCE_NAME,
            source_fixture_id=source_fixture_id,
            matched_at=datetime.now(tz=UTC),
            match_confidence=update.confidence,
            match_reason=update.reason,
        )
        session.add(row)
    else:
        row.source_fixture_id = source_fixture_id
        row.matched_at = datetime.now(tz=UTC)
        row.match_confidence = update.confidence
        row.match_reason = update.reason
    session.commit()
    return row


class ZQCF918MatchDiscoverer:
    def __init__(
        self,
        client: ZQCF918Client | None = None,
        display_names: DisplayNames | None = None,
    ) -> None:
        self.client = client or ZQCF918Client()
        self.display_service = DisplayNameService(display_names)

    def discover(self, matches: list[Match]) -> dict[int, str]:
        candidates = self.client.fetch_score_matches(type_id=1)
        return _match_candidates(matches, candidates, display_service=self.display_service)


def sync_zqcf918_match_ids_for_matches(
    session: Session,
    matches: list[Match],
    *,
    discoverer: Any | None = None,
) -> dict[str, list[dict[str, Any]] | int]:
    discoverer = discoverer or ZQCF918MatchDiscoverer()
    target_matches = [match for match in matches if get_zqcf918_match_id(session, match.id) is None]
    target_match_ids = {match.id for match in target_matches}
    skipped = [
        {"match_id": match.id, "message": "zqcf918 match ID already exists"}
        for match in matches
        if match.id not in target_match_ids
    ]
    discovered = discoverer.discover(target_matches) if target_matches else {}
    success: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for match in target_matches:
        source_fixture_id = discovered.get(match.id)
        if not source_fixture_id:
            failed.append({"match_id": match.id, "message": "zqcf918 match ID not found"})
            continue
        row = upsert_zqcf918_match_id(
            session,
            ZQCF918MatchIdUpdate(
                match_id=match.id,
                source_fixture_id=source_fixture_id,
                reason="auto:zqcf918-score-list",
                confidence=Decimal("0.9000"),
            ),
        )
        success.append(
            {
                "match_id": match.id,
                "message": "zqcf918 match ID synced",
                "source_fixture_id": row.source_fixture_id,
            }
        )
    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "requests": 1 if target_matches else 0,
        "credits": 0,
    }


def _match_candidates(
    matches: list[Match],
    candidates: list[dict[str, Any]],
    *,
    display_service: DisplayNameService,
) -> dict[int, str]:
    matched: dict[int, str] = {}
    for match in matches:
        home_names = _team_name_candidates(match.home_team.canonical_name, display_service)
        away_names = _team_name_candidates(match.away_team.canonical_name, display_service)
        league_names = _league_name_candidates(match.league.name, display_service)
        for candidate in candidates:
            candidate_id = candidate.get("ID") or candidate.get("id") or candidate.get("matchId")
            if candidate_id is None:
                continue
            if not _is_same_match_time(match, candidate):
                continue
            candidate_home_names = _candidate_team_names(candidate, ("home", "HName", "homeName"))
            candidate_away_names = _candidate_team_names(candidate, ("away", "GName", "awayName"))
            candidate_league_names = _candidate_team_names(candidate, ("league", "LName", "leagueName"))
            if not _names_match(home_names, candidate_home_names):
                continue
            if not _names_match(away_names, candidate_away_names):
                continue
            if candidate_league_names and not _names_match(league_names, candidate_league_names):
                continue
            matched[match.id] = str(candidate_id)
            break
    return matched


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        _normalized_team(value)
        for value in candidate.values()
        if isinstance(value, str)
    )


def _normalized_team(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace(".", "")
        .replace("'", "")
        .replace("’", "")
    )


def _team_name_candidates(name: str, display_service: DisplayNameService) -> list[str]:
    values = [name, display_service.display_team(name)]
    return list(dict.fromkeys(_normalized_team(value) for value in values if value))


def _league_name_candidates(name: str, display_service: DisplayNameService) -> list[str]:
    values = [name, display_service.display_league(name)]
    return list(dict.fromkeys(_normalized_team(value) for value in values if value))


def _candidate_team_names(candidate: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values = [candidate.get(key) for key in keys]
    return list(dict.fromkeys(_normalized_team(value) for value in values if isinstance(value, str) and value))


def _names_match(left_values: list[str], right_values: list[str]) -> bool:
    return any(_name_matches(left, right) for left in left_values for right in right_values)


def _name_matches(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    return _similarity(left, right) >= 0.75


def _similarity(left: str, right: str) -> float:
    max_length = max(len(left), len(right))
    if max_length == 0:
        return 1.0
    return 1 - (_levenshtein_distance(left, right) / max_length)


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def _is_same_match_time(match: Match, candidate: dict[str, Any]) -> bool:
    candidate_time = _parse_candidate_time(candidate)
    if candidate_time is None or match.kickoff_time is None:
        return True
    kickoff_time = match.kickoff_time
    if kickoff_time.tzinfo is not None:
        kickoff_time = kickoff_time.astimezone(BEIJING).replace(tzinfo=None)
    return abs((kickoff_time - candidate_time).total_seconds()) <= 3600


def _parse_candidate_time(candidate: dict[str, Any]) -> datetime | None:
    value = candidate.get("time") or candidate.get("MatchTime") or candidate.get("matchTime")
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None

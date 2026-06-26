from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import (
    ZQCF918_BASE_URL,
    ZQCF918_PINNACLE_COMPANY_ID,
    ZQCF918Client,
)


UTC = ZoneInfo("UTC")


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
    def __init__(self, client: ZQCF918Client | None = None) -> None:
        self.client = client or ZQCF918Client()

    def discover(self, matches: list[Match]) -> dict[int, str]:
        candidates = self.client.fetch_score_matches(type_id=1)
        return _match_candidates(matches, candidates)


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


def _match_candidates(matches: list[Match], candidates: list[dict[str, Any]]) -> dict[int, str]:
    matched: dict[int, str] = {}
    for match in matches:
        home_name = _normalized_team(match.home_team.canonical_name)
        away_name = _normalized_team(match.away_team.canonical_name)
        for candidate in candidates:
            candidate_id = candidate.get("ID") or candidate.get("id") or candidate.get("matchId")
            if candidate_id is None:
                continue
            candidate_text = _candidate_text(candidate)
            if home_name not in candidate_text or away_name not in candidate_text:
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
    return value.lower().replace(" ", "")

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, OddsSourceMatch
from icewine_prediction.odds_provider_selection_service import ZQCF918_SOURCE_NAME
from icewine_prediction.sources.zqcf918_client import ZQCF918_BASE_URL, ZQCF918_PINNACLE_COMPANY_ID


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

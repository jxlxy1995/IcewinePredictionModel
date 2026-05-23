from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from icewine_prediction.models import OddsSnapshot


def save_odds_snapshot(
    session: Session,
    match_id: int,
    captured_at: datetime,
    data_source: str,
    bookmaker: str,
    asian_handicap: Decimal | None,
    home_odds: Decimal | None,
    away_odds: Decimal | None,
    total_line: Decimal | None,
    over_odds: Decimal | None,
    under_odds: Decimal | None,
) -> OddsSnapshot:
    snapshot = OddsSnapshot(
        match_id=match_id,
        captured_at=captured_at,
        data_source=data_source,
        bookmaker=bookmaker,
        asian_handicap=asian_handicap,
        home_odds=home_odds,
        away_odds=away_odds,
        total_line=total_line,
        over_odds=over_odds,
        under_odds=under_odds,
    )
    session.add(snapshot)
    session.commit()
    return snapshot


def list_match_odds_snapshots(session: Session, match_id: int) -> list[OddsSnapshot]:
    return (
        session.query(OddsSnapshot)
        .filter_by(match_id=match_id)
        .order_by(OddsSnapshot.captured_at.asc())
        .all()
    )

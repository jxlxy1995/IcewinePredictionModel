from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from icewine_prediction.models import Match


def list_upcoming_matches(session: Session, start_time: datetime, hours: int) -> list[Match]:
    end_time = start_time + timedelta(hours=hours)
    return (
        session.query(Match)
        .filter(Match.status == "scheduled")
        .filter(Match.kickoff_time >= start_time)
        .filter(Match.kickoff_time <= end_time)
        .order_by(Match.kickoff_time.asc())
        .all()
    )

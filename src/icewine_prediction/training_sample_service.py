from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, OddsSnapshot
from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals
from icewine_prediction.time_utils import now_beijing


@dataclass(frozen=True)
class TrainingSample:
    match_id: int
    source_match_id: str | None
    league_name: str
    home_team_name: str
    away_team_name: str
    kickoff_time: datetime
    home_score: int
    away_score: int
    match_result: str
    total_goals: int
    asian_handicap_line: Decimal | None
    home_handicap_result: str | None
    away_handicap_result: str | None
    total_line: Decimal | None
    over_result: str | None
    under_result: str | None
    has_odds_snapshot: bool
    sample_age_days: int
    time_decay_weight: Decimal


def _match_result(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home_win"
    if home_score < away_score:
        return "away_win"
    return "draw"


def _first_snapshot(match: Match) -> OddsSnapshot | None:
    snapshots = sorted(match.odds_snapshots, key=lambda snapshot: snapshot.captured_at)
    if not snapshots:
        return None
    return snapshots[0]


def time_decay_weight_for_age(sample_age_days: int) -> Decimal:
    if sample_age_days <= 180:
        return Decimal("1.00")
    if sample_age_days <= 365:
        return Decimal("0.80")
    if sample_age_days <= 730:
        return Decimal("0.55")
    if sample_age_days <= 1095:
        return Decimal("0.35")
    return Decimal("0.15")


def build_training_sample(
    match: Match,
    reference_time: datetime | None = None,
) -> TrainingSample:
    if match.home_score is None or match.away_score is None:
        raise ValueError("training sample requires final scores")
    reference = reference_time or now_beijing()
    sample_age_days = max(0, (reference.date() - match.kickoff_time.date()).days)
    snapshot = _first_snapshot(match)
    home_handicap_result = None
    away_handicap_result = None
    over_result = None
    under_result = None
    asian_handicap_line = None
    total_line = None
    if snapshot is not None and snapshot.asian_handicap is not None:
        asian_handicap_line = snapshot.asian_handicap
        home_handicap_result = settle_asian_handicap(
            match.home_score,
            match.away_score,
            asian_handicap_line,
            "home",
        )
        away_handicap_result = settle_asian_handicap(
            match.home_score,
            match.away_score,
            asian_handicap_line,
            "away",
        )
    if snapshot is not None and snapshot.total_line is not None:
        total_line = snapshot.total_line
        over_result = settle_total_goals(match.home_score, match.away_score, total_line, "over")
        under_result = settle_total_goals(match.home_score, match.away_score, total_line, "under")
    return TrainingSample(
        match_id=match.id,
        source_match_id=match.source_match_id,
        league_name=match.league.name,
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        kickoff_time=match.kickoff_time,
        home_score=match.home_score,
        away_score=match.away_score,
        match_result=_match_result(match.home_score, match.away_score),
        total_goals=match.home_score + match.away_score,
        asian_handicap_line=asian_handicap_line,
        home_handicap_result=home_handicap_result,
        away_handicap_result=away_handicap_result,
        total_line=total_line,
        over_result=over_result,
        under_result=under_result,
        has_odds_snapshot=snapshot is not None,
        sample_age_days=sample_age_days,
        time_decay_weight=time_decay_weight_for_age(sample_age_days),
    )


def list_training_samples(
    session: Session,
    limit: int = 20,
    reference_time: datetime | None = None,
) -> list[TrainingSample]:
    matches = (
        session.query(Match)
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .order_by(Match.kickoff_time.desc())
        .limit(limit)
        .all()
    )
    return [build_training_sample(match, reference_time=reference_time) for match in matches]

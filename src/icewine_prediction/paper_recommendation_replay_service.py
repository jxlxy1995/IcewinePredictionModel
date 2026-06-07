from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.display_service import DisplayNameService
from icewine_prediction.baseline_training_dataset_service import EXCLUDED_AUXILIARY_LEAGUE_IDS
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, PaperRecommendationRecord
from icewine_prediction.paper_recommendation_queue_service import (
    PaperQueueScoreResult,
    build_paper_recommendation_rows_for_match,
    train_paper_queue_scorer_from_rows,
    _team_prior_states_by_match,
)
from icewine_prediction.paper_recommendation_tracking_service import (
    create_paper_record_from_queue_row,
    settle_paper_records,
)


PaperReplayScorerFactory = Callable[[datetime], Callable[[dict[str, str]], PaperQueueScoreResult]]


@dataclass(frozen=True)
class PaperRecommendationReplayResult:
    scanned_matches: int
    candidate_rows: int
    created_records: int
    duplicate_records: int
    settled_records: int
    skipped_settlement_records: int
    unsettleable_records: int
    records: list[PaperRecommendationRecord]


def replay_finished_matches_as_paper_recommendations(
    session: Session,
    *,
    from_time: datetime,
    to_time: datetime,
    scorer_factory: PaperReplayScorerFactory,
    recorded_at: datetime,
    edge_threshold: str = "0.10",
    settle: bool = True,
    display_name_service: DisplayNameService | None = None,
) -> PaperRecommendationReplayResult:
    matches = _list_finished_matches(session, from_time=from_time, to_time=to_time)
    team_prior_states = _team_prior_states_by_match(session, matches)
    historical_snapshots_by_match_id = _historical_snapshots_by_match_id(session, matches)
    created_records: list[PaperRecommendationRecord] = []
    candidate_rows = 0
    duplicate_records = 0
    for match in matches:
        scorer = scorer_factory(match.kickoff_time)
        rows = build_paper_recommendation_rows_for_match(
            match,
            scorer=scorer,
            edge_threshold=edge_threshold,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots_by_match_id.get(match.id, []),
            team_prior_states=team_prior_states,
        )
        for row in rows:
            if row.status != "candidate":
                continue
            candidate_rows += 1
            try:
                created_records.append(
                    create_paper_record_from_queue_row(
                        session,
                        row,
                        recorded_at=recorded_at,
                    )
                )
            except ValueError as error:
                if "duplicate active paper recommendation record" not in str(error):
                    raise
                duplicate_records += 1

    settlement = None
    if settle:
        settlement = settle_paper_records(session, settled_at=recorded_at)
        for record in created_records:
            session.refresh(record)

    return PaperRecommendationReplayResult(
        scanned_matches=len(matches),
        candidate_rows=candidate_rows,
        created_records=len(created_records),
        duplicate_records=duplicate_records,
        settled_records=settlement.settled_count if settlement is not None else 0,
        skipped_settlement_records=settlement.skipped_count if settlement is not None else 0,
        unsettleable_records=settlement.unsettleable_count if settlement is not None else 0,
        records=created_records,
    )


def build_walk_forward_replay_scorer_factory(
    feature_csv_path: Path,
) -> PaperReplayScorerFactory:
    with feature_csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    def scorer_factory(cutoff: datetime):
        train_rows = [
            row
            for row in rows
            if row.get("kickoff_time")
            and _parse_datetime(row["kickoff_time"]).replace(tzinfo=None) < cutoff.replace(tzinfo=None)
        ]
        return train_paper_queue_scorer_from_rows(train_rows)

    return scorer_factory


def _list_finished_matches(
    session: Session,
    *,
    from_time: datetime,
    to_time: datetime,
) -> list[Match]:
    return (
        session.query(Match)
        .options(
            joinedload(Match.league).joinedload(League.matches),
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.odds_snapshots),
        )
        .join(League)
        .filter(League.is_enabled.is_(True))
        .filter(
            or_(
                League.source_league_id.is_(None),
                ~League.source_league_id.in_(EXCLUDED_AUXILIARY_LEAGUE_IDS),
            )
        )
        .filter(Match.status == "finished")
        .filter(Match.home_score.isnot(None))
        .filter(Match.away_score.isnot(None))
        .filter(Match.kickoff_time >= from_time)
        .filter(Match.kickoff_time <= to_time)
        .order_by(Match.kickoff_time.asc(), Match.id.asc())
        .all()
    )


def _historical_snapshots_by_match_id(
    session: Session,
    matches: list[Match],
) -> dict[int, list[HistoricalOddsSnapshot]]:
    match_ids = [match.id for match in matches]
    if not match_ids:
        return {}
    snapshots = (
        session.query(HistoricalOddsSnapshot)
        .filter(HistoricalOddsSnapshot.match_id.in_(match_ids))
        .all()
    )
    snapshots_by_match_id: dict[int, list[HistoricalOddsSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_match_id.setdefault(snapshot.match_id, []).append(snapshot)
    return snapshots_by_match_id


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.feature_service import MatchOddsFeatures
from icewine_prediction.models import Match, RecommendationRecord
from icewine_prediction.recommendation_service import Recommendation
from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals


@dataclass(frozen=True)
class RecordGroupSummary:
    record_count: int
    stake_units: Decimal
    profit_units: Decimal
    roi: Decimal


@dataclass(frozen=True)
class RecordReport:
    total_records: int
    settled_records: int
    pending_records: int
    total_stake_units: Decimal
    total_profit_units: Decimal
    roi: Decimal
    by_settlement_result: dict[str, RecordGroupSummary]
    by_market_type: dict[str, RecordGroupSummary]
    by_confidence_grade: dict[str, RecordGroupSummary]
    by_league: dict[str, RecordGroupSummary]


def _odds_for_recommendation(
    recommendation: Recommendation,
    features: MatchOddsFeatures,
) -> Decimal | None:
    if recommendation.side == "home":
        return features.home_odds.mean
    if recommendation.side == "away":
        return features.away_odds.mean
    if recommendation.side == "over":
        return features.over_odds.mean
    if recommendation.side == "under":
        return features.under_odds.mean
    return None


def _has_duplicate_pending_record(
    session: Session,
    match_id: int,
    recommendation: Recommendation,
) -> bool:
    return (
        session.query(RecommendationRecord)
        .filter(RecommendationRecord.match_id == match_id)
        .filter(RecommendationRecord.market_type == recommendation.market_type)
        .filter(RecommendationRecord.side == recommendation.side)
        .filter(RecommendationRecord.market_line == recommendation.market_line)
        .filter(RecommendationRecord.status == "pending")
        .first()
        is not None
    )


def record_recommendations_for_match(
    session: Session,
    match: Match,
    recommendations: list[Recommendation],
    features: MatchOddsFeatures,
    recorded_at: datetime,
) -> int:
    inserted_count = 0
    for recommendation in recommendations:
        odds = _odds_for_recommendation(recommendation, features)
        if not recommendation.should_bet or recommendation.market_line is None or odds is None:
            continue
        if _has_duplicate_pending_record(session, match.id, recommendation):
            continue
        session.add(
            RecommendationRecord(
                match_id=match.id,
                created_at=recorded_at,
                league_name=match.league.name,
                home_team_name=match.home_team.canonical_name,
                away_team_name=match.away_team.canonical_name,
                kickoff_time=match.kickoff_time,
                market_type=recommendation.market_type,
                side=recommendation.side,
                market_line=recommendation.market_line,
                odds=odds,
                model_probability=recommendation.model_probability,
                market_implied_probability=recommendation.market_implied_probability,
                edge=recommendation.edge,
                confidence_grade=recommendation.confidence_grade,
                stake_units=recommendation.stake_units,
                home_expected_goals=recommendation.home_expected_goals,
                away_expected_goals=recommendation.away_expected_goals,
                status="pending",
            )
        )
        inserted_count += 1
    session.commit()
    return inserted_count


def list_pending_records(session: Session) -> list[RecommendationRecord]:
    return (
        session.query(RecommendationRecord)
        .filter(RecommendationRecord.status == "pending")
        .order_by(RecommendationRecord.kickoff_time.asc())
        .all()
    )


def profit_units_for_result(
    settlement_result: str,
    stake_units: Decimal,
    odds: Decimal,
) -> Decimal:
    if settlement_result == "win":
        profit = stake_units * (odds - Decimal("1"))
    elif settlement_result == "half_win":
        profit = stake_units * Decimal("0.5") * (odds - Decimal("1"))
    elif settlement_result == "push":
        profit = Decimal("0")
    elif settlement_result == "half_loss":
        profit = -stake_units * Decimal("0.5")
    elif settlement_result == "loss":
        profit = -stake_units
    else:
        raise ValueError(f"unknown settlement result: {settlement_result}")
    return profit.quantize(Decimal("0.001"))


def _settle_record(record: RecommendationRecord) -> str:
    match = record.match
    if match.home_score is None or match.away_score is None:
        raise ValueError("record match has no final score")
    if record.market_type == "asian_handicap":
        return settle_asian_handicap(
            match.home_score,
            match.away_score,
            record.market_line,
            record.side,
        )
    if record.market_type == "total_goals":
        return settle_total_goals(
            match.home_score,
            match.away_score,
            record.market_line,
            record.side,
        )
    raise ValueError(f"unknown market type: {record.market_type}")


def settle_pending_records(session: Session) -> int:
    records = list_pending_records(session)
    settled_count = 0
    for record in records:
        if record.match.home_score is None or record.match.away_score is None:
            continue
        settlement_result = _settle_record(record)
        record.settlement_result = settlement_result
        record.profit_units = profit_units_for_result(
            settlement_result,
            record.stake_units,
            record.odds,
        )
        record.status = "settled"
        settled_count += 1
    session.commit()
    return settled_count


def _round_units(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _round_stake(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


def _round_roi(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _summarize_records(records: list[RecommendationRecord]) -> RecordGroupSummary:
    stake_units = sum((record.stake_units for record in records), Decimal("0"))
    profit_units = sum((record.profit_units or Decimal("0") for record in records), Decimal("0"))
    roi = Decimal("0")
    if stake_units != Decimal("0"):
        roi = profit_units / stake_units
    return RecordGroupSummary(
        record_count=len(records),
        stake_units=_round_stake(stake_units),
        profit_units=_round_units(profit_units),
        roi=_round_roi(roi),
    )


def _group_records(
    records: list[RecommendationRecord],
    key_name: str,
) -> dict[str, RecordGroupSummary]:
    grouped: dict[str, list[RecommendationRecord]] = {}
    for record in records:
        key = getattr(record, key_name)
        grouped.setdefault(key, []).append(record)
    return {key: _summarize_records(value) for key, value in grouped.items()}


def build_record_report(session: Session) -> RecordReport:
    records = session.query(RecommendationRecord).all()
    settled_records = [record for record in records if record.status == "settled"]
    total_summary = _summarize_records(settled_records)
    return RecordReport(
        total_records=len(records),
        settled_records=len(settled_records),
        pending_records=len([record for record in records if record.status == "pending"]),
        total_stake_units=total_summary.stake_units,
        total_profit_units=total_summary.profit_units,
        roi=total_summary.roi,
        by_settlement_result=_group_records(settled_records, "settlement_result"),
        by_market_type=_group_records(settled_records, "market_type"),
        by_confidence_grade=_group_records(settled_records, "confidence_grade"),
        by_league=_group_records(settled_records, "league_name"),
    )

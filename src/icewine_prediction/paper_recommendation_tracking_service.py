from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.models import Match, PaperRecommendationRecord
from icewine_prediction.paper_recommendation_queue_service import PaperQueueRow
from icewine_prediction.paper_strategy_registry import (
    ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME,
    STRATEGIES,
    PaperStrategy,
    strategy_for_key,
)
from icewine_prediction.record_service import profit_units_for_result
from icewine_prediction.settlement_service import settle_asian_handicap, settle_total_goals


ACTIVE_STATUSES = ("pending", "settled", "unsettleable")


@dataclass(frozen=True)
class PaperTrackingSummary:
    total_records: int
    pending_records: int
    settled_records: int
    void_records: int
    candidate_count: int
    total_stake_units: Decimal
    total_profit_units: Decimal
    hit_rate: Decimal
    roi: Decimal


@dataclass(frozen=True)
class PaperTrackingGroupSummary:
    group_name: str
    record_count: int
    settled_records: int
    total_stake_units: Decimal
    total_profit_units: Decimal
    hit_rate: Decimal
    roi: Decimal


@dataclass(frozen=True)
class PaperSettlementResult:
    settled_count: int
    skipped_count: int
    unsettleable_count: int


@dataclass(frozen=True)
class PaperTrackingWorkspace:
    strategies: list[PaperStrategy]
    candidates: list[PaperQueueRow]
    records: list[PaperRecommendationRecord]
    summary: PaperTrackingSummary
    by_strategy: list[PaperTrackingGroupSummary]
    by_league: list[PaperTrackingGroupSummary]
    by_line_bucket: list[PaperTrackingGroupSummary]
    by_manual_adjustment: list[PaperTrackingGroupSummary]


def create_paper_record_from_queue_row(
    session: Session,
    row: PaperQueueRow,
    *,
    recorded_at: datetime,
) -> PaperRecommendationRecord:
    _validate_recordable_candidate(row)
    strategy = strategy_for_key(row.strategy_key)
    if strategy is None:
        raise ValueError("paper record strategy is not open")
    if _has_duplicate_active_record(session, row):
        raise ValueError("duplicate active paper recommendation record")
    match = session.get(Match, row.match_id)
    if match is None:
        raise ValueError(f"match not found: {row.match_id}")
    record = PaperRecommendationRecord(
        match_id=row.match_id,
        source_match_id=row.source_match_id,
        created_at=recorded_at,
        updated_at=recorded_at,
        league_name=row.league_name,
        league_display_name=row.league_display_name,
        home_team_name=row.home_team_name,
        home_team_display_name=row.home_team_display_name,
        away_team_name=row.away_team_name,
        away_team_display_name=row.away_team_display_name,
        kickoff_time=match.kickoff_time,
        strategy_key=row.strategy_key,
        strategy_display_name=row.strategy_display_name,
        model_name=strategy.model_name,
        signal_version=row.signal_version,
        market_type=row.market_type,
        side=row.side or "",
        recommended_handicap=row.recommended_handicap,
        original_recommended_handicap=row.recommended_handicap,
        line_bucket=row.line_bucket,
        risk_tags=",".join(row.risk_tags),
        original_market_line=_required_decimal(row.line, "line"),
        original_odds=_required_decimal(row.odds, "odds"),
        current_market_line=_required_decimal(row.line, "line"),
        current_odds=_required_decimal(row.odds, "odds"),
        model_probability=row.model_probability,
        market_probability=row.market_probability,
        edge=_required_decimal(row.edge, "edge"),
        stake_units=Decimal("1.00"),
        status="pending",
        is_manually_adjusted=False,
    )
    session.add(record)
    session.commit()
    return record


def backfill_paper_record_from_candidate(
    session: Session,
    *,
    match_id: int,
    recorded_at: datetime,
    market_line: Decimal,
    odds: Decimal,
    model_probability: Decimal,
    market_probability: Decimal,
    edge: Decimal,
    manual_note: str,
    league_display_name: str | None = None,
    home_team_display_name: str | None = None,
    away_team_display_name: str | None = None,
) -> PaperRecommendationRecord:
    match = session.get(Match, match_id)
    if match is None:
        raise ValueError(f"match not found: {match_id}")
    league_name = match.league.name
    home_team_name = match.home_team.canonical_name
    away_team_name = match.away_team.canonical_name
    row = PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time=match.kickoff_time.isoformat(),
        league_name=league_name,
        league_display_name=league_display_name or league_name,
        home_team_name=home_team_name,
        home_team_display_name=home_team_display_name or home_team_name,
        away_team_name=away_team_name,
        away_team_display_name=away_team_display_name or away_team_name,
        status="candidate",
        market_type="asian_handicap",
        line=market_line,
        side="away_cover",
        recommended_handicap=recommended_handicap("away_cover", market_line),
        odds=odds,
        model_probability=model_probability,
        market_probability=market_probability,
        edge=edge,
        line_bucket=_line_bucket(market_line),
        risk_tags=("manual_backfill", _line_bucket(market_line)),
    )
    record = create_paper_record_from_queue_row(session, row, recorded_at=recorded_at)
    record.manual_note = manual_note
    record.is_manually_adjusted = True
    session.commit()
    return record


def edit_paper_record(
    session: Session,
    record_id: int,
    *,
    current_market_line: Decimal,
    current_odds: Decimal,
    manual_note: str | None,
) -> PaperRecommendationRecord:
    record = _get_record(session, record_id)
    if record.status not in ("pending", "unsettleable"):
        raise ValueError("only pending or unsettleable paper records can be edited")
    record.current_market_line = current_market_line
    record.current_odds = current_odds
    record.recommended_handicap = recommended_for_market(
        record.market_type,
        record.side,
        current_market_line,
    )
    record.manual_note = manual_note
    record.is_manually_adjusted = True
    record.updated_at = datetime.now(tz=record.created_at.tzinfo)
    if record.status == "unsettleable":
        record.status = "pending"
    session.commit()
    return record


def void_paper_record(session: Session, record_id: int) -> PaperRecommendationRecord:
    record = _get_record(session, record_id)
    record.status = "void"
    record.updated_at = datetime.now(tz=record.created_at.tzinfo)
    session.commit()
    return record


def settle_paper_records(session: Session, *, settled_at: datetime) -> PaperSettlementResult:
    records = (
        session.query(PaperRecommendationRecord)
        .filter(PaperRecommendationRecord.status.in_(("pending", "unsettleable")))
        .all()
    )
    settled_count = skipped_count = unsettleable_count = 0
    for record in records:
        match = record.match
        if match.home_score is None or match.away_score is None:
            skipped_count += 1
            if match.status == "finished":
                record.status = "unsettleable"
                unsettleable_count += 1
            continue
        if record.market_type == "asian_handicap":
            settlement_result = settle_asian_handicap(
                match.home_score,
                match.away_score,
                record.current_market_line,
                _settlement_side(record.side),
            )
        elif record.market_type == "total_goals":
            settlement_result = settle_total_goals(
                match.home_score,
                match.away_score,
                record.current_market_line,
                record.side,
            )
        else:
            record.status = "unsettleable"
            unsettleable_count += 1
            continue
        record.settlement_result = settlement_result
        record.profit_units = profit_units_for_result(
            settlement_result,
            record.stake_units,
            record.current_odds,
        )
        record.status = "settled"
        record.settled_at = settled_at
        record.updated_at = settled_at
        settled_count += 1
    session.commit()
    return PaperSettlementResult(
        settled_count=settled_count,
        skipped_count=skipped_count,
        unsettleable_count=unsettleable_count,
    )


def build_paper_tracking_workspace(
    session: Session,
    *,
    candidates: list[PaperQueueRow],
) -> PaperTrackingWorkspace:
    records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.desc(), PaperRecommendationRecord.id.desc())
        .all()
    )
    return PaperTrackingWorkspace(
        strategies=list(STRATEGIES),
        candidates=candidates,
        records=records,
        summary=_summarize(records, candidate_count=len(candidates)),
        by_strategy=_group(records, _current_strategy_display_name),
        by_league=_group(records, lambda record: record.league_display_name or record.league_name),
        by_line_bucket=_group(records, lambda record: record.line_bucket or "unknown"),
        by_manual_adjustment=_group(
            records,
            lambda record: "人工调整" if record.is_manually_adjusted else "原始记录",
        ),
    )


def recommended_handicap(side: str | None, line: Decimal | None) -> str | None:
    if side is None or line is None:
        return None
    if side == "home_cover":
        return f"主队 {_format_signed_line(line)}"
    if side == "away_cover":
        return f"客队 {_format_signed_line(-line)}"
    return None


def recommended_for_market(
    market_type: str,
    side: str | None,
    line: Decimal | None,
) -> str | None:
    if market_type == "total_goals":
        return recommended_total_goals(side, line)
    return recommended_handicap(side, line)


def recommended_total_goals(side: str | None, line: Decimal | None) -> str | None:
    if side is None or line is None:
        return None
    if side == "over":
        return f"大 {_format_line(line)}"
    if side == "under":
        return f"小 {_format_line(line)}"
    return None


def _validate_recordable_candidate(row: PaperQueueRow) -> None:
    if row.status != "candidate":
        raise ValueError("paper record can only be created from candidate rows")
    strategy = strategy_for_key(row.strategy_key)
    if strategy is None:
        raise ValueError("paper record strategy is not open")
    if row.market_type != strategy.market_type or (
        strategy.side is not None and row.side != strategy.side
    ):
        raise ValueError("paper record does not match the open strategy")
    if row.edge is None or row.edge < strategy.edge_threshold:
        raise ValueError("paper record edge is below strategy threshold")
    if row.line is None or row.odds is None:
        raise ValueError("paper record requires line and odds")


def _line_bucket(line: Decimal | None) -> str:
    if line is None:
        return "unknown"
    if line > 0:
        return "away_favorite"
    if line == 0:
        return "pickem"
    return "away_underdog"


def _settlement_side(side: str) -> str:
    side_map = {
        "away_cover": "away",
        "home_cover": "home",
    }
    if side not in side_map:
        raise ValueError(f"unsupported paper recommendation side: {side}")
    return side_map[side]


def _has_duplicate_active_record(session: Session, row: PaperQueueRow) -> bool:
    return (
        session.query(PaperRecommendationRecord)
        .filter(PaperRecommendationRecord.match_id == row.match_id)
        .filter(PaperRecommendationRecord.strategy_key == row.strategy_key)
        .filter(PaperRecommendationRecord.market_type == row.market_type)
        .filter(PaperRecommendationRecord.side == row.side)
        .filter(PaperRecommendationRecord.status.in_(ACTIVE_STATUSES))
        .first()
        is not None
    )


def _get_record(session: Session, record_id: int) -> PaperRecommendationRecord:
    record = session.get(PaperRecommendationRecord, record_id)
    if record is None:
        raise ValueError(f"paper recommendation record not found: {record_id}")
    return record


def _summarize(
    records: list[PaperRecommendationRecord],
    *,
    candidate_count: int,
) -> PaperTrackingSummary:
    settled = _settled_records(records)
    total_stake = _sum_decimal(record.stake_units for record in settled)
    total_profit = _sum_decimal(record.profit_units or Decimal("0") for record in settled)
    return PaperTrackingSummary(
        total_records=len(records),
        pending_records=len([record for record in records if record.status == "pending"]),
        settled_records=len(settled),
        void_records=len([record for record in records if record.status == "void"]),
        candidate_count=candidate_count,
        total_stake_units=_quantize(total_stake, Decimal("0.00")),
        total_profit_units=_quantize(total_profit, Decimal("0.001")),
        hit_rate=_ratio(_hit_count(settled), len(settled)),
        roi=_ratio(total_profit, total_stake),
    )


def _group(
    records: list[PaperRecommendationRecord],
    group_key,
) -> list[PaperTrackingGroupSummary]:
    grouped: dict[str, list[PaperRecommendationRecord]] = {}
    for record in records:
        if record.status in ("void", "unsettleable"):
            continue
        grouped.setdefault(group_key(record), []).append(record)
    summaries = []
    for group_name, group_records in grouped.items():
        settled = _settled_records(group_records)
        total_stake = _sum_decimal(record.stake_units for record in settled)
        total_profit = _sum_decimal(record.profit_units or Decimal("0") for record in settled)
        summaries.append(
            PaperTrackingGroupSummary(
                group_name=group_name,
                record_count=len(group_records),
                settled_records=len(settled),
                total_stake_units=_quantize(total_stake, Decimal("0.00")),
                total_profit_units=_quantize(total_profit, Decimal("0.001")),
                hit_rate=_ratio(_hit_count(settled), len(settled)),
                roi=_ratio(total_profit, total_stake),
            )
        )
    return sorted(summaries, key=lambda item: (item.group_name != "人工调整", item.group_name))


def _current_strategy_display_name(record: PaperRecommendationRecord) -> str:
    strategy = strategy_for_key(record.strategy_key)
    if strategy is not None:
        return strategy.display_name
    return record.strategy_display_name


def _settled_records(records: list[PaperRecommendationRecord]) -> list[PaperRecommendationRecord]:
    return [record for record in records if record.status == "settled"]


def _hit_count(records: list[PaperRecommendationRecord]) -> int:
    return len([record for record in records if record.settlement_result in ("win", "half_win")])


def _ratio(numerator: Decimal | int, denominator: Decimal | int) -> Decimal:
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal == 0:
        return Decimal("0.0000")
    return _quantize(Decimal(str(numerator)) / denominator_decimal, Decimal("0.0000"))


def _sum_decimal(values) -> Decimal:
    return sum(values, Decimal("0"))


def _required_decimal(value: Decimal | None, field_name: str) -> Decimal:
    if value is None:
        raise ValueError(f"paper record requires {field_name}")
    return value


def _format_signed_line(value: Decimal) -> str:
    if value > 0:
        return f"+{_format_line(value)}"
    return _format_line(value)


def _format_line(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


def _quantize(value: Decimal, quant: Decimal) -> Decimal:
    return value.quantize(quant, rounding=ROUND_HALF_UP)

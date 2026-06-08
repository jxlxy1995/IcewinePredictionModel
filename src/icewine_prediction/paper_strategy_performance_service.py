from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.models import PaperRecommendationRecord
from icewine_prediction.paper_strategy_registry import strategy_for_key


MONEY_QUANT = Decimal("0.001")
RATIO_QUANT = Decimal("0.0000")
STAKE_QUANT = Decimal("0.00")
LOW_SAMPLE_THRESHOLD = 20


@dataclass(frozen=True)
class PaperStrategyPerformanceFilters:
    start_time: datetime | None = None
    end_time: datetime | None = None
    strategy_key: str | None = None
    market_type: str | None = None
    side: str | None = None
    league_name: str | None = None
    line_bucket: str | None = None
    manual_adjustment: bool | None = None


@dataclass(frozen=True)
class PaperStrategyPerformanceSummary:
    total_records: int
    active_records: int
    settled_records: int
    pending_records: int
    void_records: int
    total_stake_units: Decimal
    total_profit_units: Decimal
    hit_rate: Decimal
    roi: Decimal
    low_sample_group_count: int


@dataclass(frozen=True)
class PaperStrategyPerformanceGroup:
    group_key: str
    group_name: str
    record_count: int
    settled_records: int
    pending_records: int
    total_stake_units: Decimal
    total_profit_units: Decimal
    hit_rate: Decimal
    roi: Decimal
    average_edge: Decimal
    average_scoring_edge: Decimal | None
    warning: str | None


@dataclass(frozen=True)
class PaperStrategyPerformanceReport:
    summary: PaperStrategyPerformanceSummary
    by_strategy: list[PaperStrategyPerformanceGroup]
    by_market_side: list[PaperStrategyPerformanceGroup]
    by_league: list[PaperStrategyPerformanceGroup]
    by_line_bucket: list[PaperStrategyPerformanceGroup]
    by_manual_adjustment: list[PaperStrategyPerformanceGroup]
    by_edge_bucket: list[PaperStrategyPerformanceGroup]
    by_settlement_result: list[PaperStrategyPerformanceGroup]


def build_paper_strategy_performance_report(
    session: Session,
    filters: PaperStrategyPerformanceFilters | None = None,
) -> PaperStrategyPerformanceReport:
    active_filters = filters or PaperStrategyPerformanceFilters()
    records = [
        record
        for record in session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.kickoff_time.asc(), PaperRecommendationRecord.id.asc())
        .all()
        if _matches_filters(record, active_filters)
    ]
    settled = _settled_records(records)
    by_strategy = _group_records(
        settled,
        lambda record: record.strategy_key,
        _strategy_display_name,
    )
    by_market_side = _group_records(
        settled,
        lambda record: f"{record.market_type}:{record.side}",
        lambda record: f"{_market_type_label(record.market_type)} / {_side_label(record.side)}",
    )
    by_league = _group_records(
        settled,
        lambda record: record.league_name,
        lambda record: record.league_display_name or record.league_name,
    )
    by_line_bucket = _group_records(
        settled,
        lambda record: record.line_bucket or "unknown",
        lambda record: record.line_bucket or "unknown",
    )
    by_manual_adjustment = _group_records(
        settled,
        lambda record: "manual_adjusted" if record.is_manually_adjusted else "original",
        lambda record: "人工调整" if record.is_manually_adjusted else "原始记录",
        sort_key=lambda group: (group.group_key != "manual_adjusted", group.group_key),
    )
    by_edge_bucket = _group_records(
        settled,
        lambda record: edge_bucket_for_record(record),
        lambda record: edge_bucket_for_record(record),
    )
    by_settlement_result = _group_records(
        settled,
        lambda record: record.settlement_result or "unknown",
        lambda record: _settlement_result_label(record.settlement_result),
    )
    low_sample_group_count = sum(
        1
        for group in (
            by_strategy
            + by_market_side
            + by_league
            + by_line_bucket
            + by_manual_adjustment
            + by_edge_bucket
        )
        if group.warning == "low_sample"
    )
    return PaperStrategyPerformanceReport(
        summary=_summarize(records, low_sample_group_count=low_sample_group_count),
        by_strategy=by_strategy,
        by_market_side=by_market_side,
        by_league=by_league,
        by_line_bucket=by_line_bucket,
        by_manual_adjustment=by_manual_adjustment,
        by_edge_bucket=by_edge_bucket,
        by_settlement_result=by_settlement_result,
    )


def edge_bucket_for_record(record: PaperRecommendationRecord) -> str:
    edge = record.scoring_edge if record.scoring_edge is not None else record.edge
    if edge < Decimal("0.03"):
        return "0.00-0.03"
    if edge < Decimal("0.06"):
        return "0.03-0.06"
    if edge < Decimal("0.10"):
        return "0.06-0.10"
    return "0.10+"


def _matches_filters(
    record: PaperRecommendationRecord,
    filters: PaperStrategyPerformanceFilters,
) -> bool:
    kickoff_time = _comparable_datetime(record.kickoff_time)
    if filters.start_time is not None and kickoff_time < _comparable_datetime(filters.start_time):
        return False
    if filters.end_time is not None and kickoff_time > _comparable_datetime(filters.end_time):
        return False
    if filters.strategy_key is not None and record.strategy_key != filters.strategy_key:
        return False
    if filters.market_type is not None and record.market_type != filters.market_type:
        return False
    if filters.side is not None and record.side != filters.side:
        return False
    if filters.league_name is not None and record.league_name != filters.league_name:
        return False
    if filters.line_bucket is not None and record.line_bucket != filters.line_bucket:
        return False
    if (
        filters.manual_adjustment is not None
        and record.is_manually_adjusted != filters.manual_adjustment
    ):
        return False
    return True


def _summarize(
    records: list[PaperRecommendationRecord],
    *,
    low_sample_group_count: int,
) -> PaperStrategyPerformanceSummary:
    active = [record for record in records if record.status != "void"]
    settled = _settled_records(records)
    total_stake = _sum_decimal(record.stake_units for record in settled)
    total_profit = _sum_decimal(record.profit_units or Decimal("0") for record in settled)
    return PaperStrategyPerformanceSummary(
        total_records=len(records),
        active_records=len(active),
        settled_records=len(settled),
        pending_records=len([record for record in records if record.status == "pending"]),
        void_records=len([record for record in records if record.status == "void"]),
        total_stake_units=_quantize(total_stake, STAKE_QUANT),
        total_profit_units=_quantize(total_profit, MONEY_QUANT),
        hit_rate=_ratio(_hit_count(settled), len(settled)),
        roi=_ratio(total_profit, total_stake),
        low_sample_group_count=low_sample_group_count,
    )


def _group_records(
    records: list[PaperRecommendationRecord],
    key_func,
    name_func,
    *,
    sort_key=None,
) -> list[PaperStrategyPerformanceGroup]:
    grouped: dict[str, list[PaperRecommendationRecord]] = {}
    names: dict[str, str] = {}
    for record in records:
        key = key_func(record)
        grouped.setdefault(key, []).append(record)
        names.setdefault(key, name_func(record))
    groups = [
        _summarize_group(key, names[key], group_records)
        for key, group_records in grouped.items()
    ]
    return sorted(groups, key=sort_key or (lambda group: group.group_key))


def _summarize_group(
    key: str,
    name: str,
    records: list[PaperRecommendationRecord],
) -> PaperStrategyPerformanceGroup:
    settled = _settled_records(records)
    total_stake = _sum_decimal(record.stake_units for record in settled)
    total_profit = _sum_decimal(record.profit_units or Decimal("0") for record in settled)
    scoring_edges = [
        record.scoring_edge
        for record in records
        if record.scoring_edge is not None
    ]
    return PaperStrategyPerformanceGroup(
        group_key=key,
        group_name=name,
        record_count=len(records),
        settled_records=len(settled),
        pending_records=len([record for record in records if record.status == "pending"]),
        total_stake_units=_quantize(total_stake, STAKE_QUANT),
        total_profit_units=_quantize(total_profit, MONEY_QUANT),
        hit_rate=_ratio(_hit_count(settled), len(settled)),
        roi=_ratio(total_profit, total_stake),
        average_edge=_average_decimal([record.edge for record in records]),
        average_scoring_edge=(
            _average_decimal(scoring_edges) if scoring_edges else None
        ),
        warning="low_sample" if 0 < len(settled) < LOW_SAMPLE_THRESHOLD else None,
    )


def _strategy_display_name(record: PaperRecommendationRecord) -> str:
    strategy = strategy_for_key(record.strategy_key)
    if strategy is not None:
        return strategy.display_name
    return record.strategy_display_name


def _market_type_label(value: str) -> str:
    labels = {
        "asian_handicap": "亚盘",
        "total_goals": "大小球",
        "match_winner": "胜平负",
    }
    return labels.get(value, value)


def _side_label(value: str) -> str:
    labels = {
        "away_cover": "客队方向",
        "home_cover": "主队方向",
        "over": "大球",
        "under": "小球",
    }
    return labels.get(value, value)


def _settlement_result_label(value: str | None) -> str:
    labels = {
        "half_loss": "输半",
        "half_win": "赢半",
        "loss": "输",
        "push": "走水",
        "win": "赢",
    }
    if value is None:
        return "未知"
    return labels.get(value, value)


def _settled_records(records: list[PaperRecommendationRecord]) -> list[PaperRecommendationRecord]:
    return [record for record in records if record.status == "settled"]


def _hit_count(records: list[PaperRecommendationRecord]) -> int:
    return len([record for record in records if record.settlement_result in ("win", "half_win")])


def _average_decimal(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return _quantize(sum(values, Decimal("0")) / Decimal(len(values)), RATIO_QUANT)


def _ratio(numerator: Decimal | int, denominator: Decimal | int) -> Decimal:
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal == 0:
        return Decimal("0.0000")
    return _quantize(Decimal(str(numerator)) / denominator_decimal, RATIO_QUANT)


def _sum_decimal(values) -> Decimal:
    return sum(values, Decimal("0"))


def _quantize(value: Decimal, quant: Decimal) -> Decimal:
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def _comparable_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)

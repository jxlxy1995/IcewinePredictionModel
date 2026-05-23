from dataclasses import dataclass

from sqlalchemy.orm import Session

from icewine_prediction.models import RecommendationRecord
from icewine_prediction.record_service import (
    RecordGroupSummary,
    _group_records,
    _group_records_by_edge_bucket,
    _summarize_records,
    edge_bucket_for_value,
)


@dataclass(frozen=True)
class HistoricalPerformanceFilters:
    market_type: str | None = None
    side: str | None = None
    league_name: str | None = None
    edge_bucket: str | None = None
    confidence_grade: str | None = None


@dataclass(frozen=True)
class HistoricalPerformanceReport:
    total: RecordGroupSummary
    by_settlement_result: dict[str, RecordGroupSummary]
    by_edge_bucket: dict[str, RecordGroupSummary]
    by_market_type: dict[str, RecordGroupSummary]
    by_side: dict[str, RecordGroupSummary]
    by_confidence_grade: dict[str, RecordGroupSummary]
    by_league: dict[str, RecordGroupSummary]


def _matches_filters(
    record: RecommendationRecord,
    filters: HistoricalPerformanceFilters,
) -> bool:
    if filters.market_type is not None and record.market_type != filters.market_type:
        return False
    if filters.side is not None and record.side != filters.side:
        return False
    if filters.league_name is not None and record.league_name != filters.league_name:
        return False
    if (
        filters.edge_bucket is not None
        and edge_bucket_for_value(record.edge) != filters.edge_bucket
    ):
        return False
    if (
        filters.confidence_grade is not None
        and record.confidence_grade != filters.confidence_grade
    ):
        return False
    return True


def build_historical_performance_report(
    session: Session,
    filters: HistoricalPerformanceFilters | None = None,
) -> HistoricalPerformanceReport:
    active_filters = filters or HistoricalPerformanceFilters()
    records = (
        session.query(RecommendationRecord)
        .filter(RecommendationRecord.status == "settled")
        .all()
    )
    filtered_records = [
        record for record in records if _matches_filters(record, active_filters)
    ]
    return HistoricalPerformanceReport(
        total=_summarize_records(filtered_records),
        by_settlement_result=_group_records(filtered_records, "settlement_result"),
        by_edge_bucket=_group_records_by_edge_bucket(filtered_records),
        by_market_type=_group_records(filtered_records, "market_type"),
        by_side=_group_records(filtered_records, "side"),
        by_confidence_grade=_group_records(filtered_records, "confidence_grade"),
        by_league=_group_records(filtered_records, "league_name"),
    )

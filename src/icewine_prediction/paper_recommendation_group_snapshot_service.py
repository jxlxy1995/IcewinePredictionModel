from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from icewine_prediction.models import (
    PaperRecommendationGroupSnapshot,
    PaperRecommendationRecord,
)
from icewine_prediction.paper_confidence_service import (
    PaperConfidenceGroup,
    build_paper_confidence_workspace,
)


PAPER_CONFIDENCE_SNAPSHOT_VERSION = "paper_confidence_v1"
MONEY_QUANT = Decimal("0.001")
RATIO_QUANT = Decimal("0.0000")
STAKE_QUANT = Decimal("0.00")
HISTORICAL_BACKFILL_SOURCE = "historical_backfill"


@dataclass(frozen=True)
class CreatedPaperGroupSnapshot:
    snapshot: PaperRecommendationGroupSnapshot
    group: PaperConfidenceGroup


@dataclass(frozen=True)
class SnapshotBackfillResult:
    record_count: int
    candidate_group_count: int
    created_count: int
    skipped_count: int
    dry_run: bool


@dataclass(frozen=True)
class _SnapshotBackfillCounts:
    candidate_group_count: int
    creatable_group_count: int
    existing_group_count: int


@dataclass(frozen=True)
class SnapshotReportSummary:
    group_count: int
    settled_groups: int
    pending_groups: int
    suggested_stake_units: Decimal
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class SnapshotReportGroup:
    group_name: str
    group_count: int
    settled_groups: int
    pending_groups: int
    suggested_stake_units: Decimal
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class SnapshotReport:
    summary: SnapshotReportSummary
    by_market_line_bucket: dict[str, SnapshotReportGroup]
    by_market_stake_bucket: dict[str, SnapshotReportGroup]
    by_snapshot_source: dict[str, SnapshotReportGroup]


def create_group_snapshots_for_record_ids(
    session: Session,
    record_ids: list[int],
    *,
    snapshot_source: str,
    created_at: datetime,
    snapshot_version: str = PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    is_backfilled: bool = False,
) -> list[CreatedPaperGroupSnapshot]:
    if not record_ids:
        return []
    record_id_set = set(record_ids)
    all_records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    workspace = build_paper_confidence_workspace(all_records)
    created: list[CreatedPaperGroupSnapshot] = []
    for group in workspace.groups:
        if not record_id_set.intersection(group.signal_record_ids):
            continue
        signal_record_ids = tuple(sorted(group.signal_record_ids))
        signal_record_id_set = set(signal_record_ids)
        signal_record_ids_json = _json_list(signal_record_ids)
        if _snapshot_exists(
            session,
            snapshot_source=snapshot_source,
            snapshot_version=snapshot_version,
            group_key=group.group_key,
            signal_record_ids_json=signal_record_ids_json,
        ):
            continue
        group_records = [
            record
            for record in all_records
            if record.id in signal_record_id_set
        ]
        source_times = [record.created_at for record in group_records]
        snapshot = PaperRecommendationGroupSnapshot(
            created_at=created_at,
            snapshot_source=snapshot_source,
            snapshot_version=snapshot_version,
            group_key=group.group_key,
            match_id=group.match_id,
            market_type=group.market_type,
            side=group.logical_side,
            representative_record_id=group.representative_record_id,
            signal_record_ids_json=signal_record_ids_json,
            triggered_strategy_keys_json=_json_list(group.triggered_strategy_keys),
            triggered_strategy_display_names_json=_json_list(group.triggered_strategy_display_names),
            signal_families_json=_json_list(group.signal_families),
            confidence_score=group.confidence_score,
            suggested_stake_units=group.suggested_stake_units,
            stake_cap_reason=group.stake_cap_reason,
            recommendation_text=group.recommendation_text,
            representative_market_line=group.representative_market_line,
            representative_odds=group.representative_odds,
            line_bucket=_line_bucket_for_group(group_records, group.representative_record_id),
            status=group.status,
            settlement_result=group.settlement_result,
            flat_profit_units=group.flat_profit_units.quantize(MONEY_QUANT),
            weighted_profit_units=group.weighted_profit_units.quantize(MONEY_QUANT),
            is_backfilled=is_backfilled,
            source_record_created_at_min=min(source_times),
            source_record_created_at_max=max(source_times),
        )
        try:
            with session.begin_nested():
                session.add(snapshot)
                session.flush()
        except IntegrityError:
            if _snapshot_exists(
                session,
                snapshot_source=snapshot_source,
                snapshot_version=snapshot_version,
                group_key=group.group_key,
                signal_record_ids_json=signal_record_ids_json,
            ):
                continue
            raise
        created.append(CreatedPaperGroupSnapshot(snapshot=snapshot, group=group))
    session.commit()
    return created


def backfill_group_snapshots(
    session: Session,
    *,
    from_date: datetime,
    to_date: datetime,
    created_at: datetime,
    snapshot_source: str = HISTORICAL_BACKFILL_SOURCE,
    snapshot_version: str = PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    dry_run: bool = False,
) -> SnapshotBackfillResult:
    records = (
        session.query(PaperRecommendationRecord)
        .filter(PaperRecommendationRecord.created_at >= from_date)
        .filter(PaperRecommendationRecord.created_at <= to_date)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    record_ids = [record.id for record in records]
    counts = _count_backfill_groups(
        session,
        record_ids,
        snapshot_source=snapshot_source,
        snapshot_version=snapshot_version,
    )
    if dry_run:
        created_count = counts.creatable_group_count
    else:
        created_count = len(
            create_group_snapshots_for_record_ids(
                session,
                record_ids,
                snapshot_source=snapshot_source,
                snapshot_version=snapshot_version,
                created_at=created_at,
                is_backfilled=True,
            )
        )
    return SnapshotBackfillResult(
        record_count=len(records),
        candidate_group_count=counts.candidate_group_count,
        created_count=created_count,
        skipped_count=max(0, counts.candidate_group_count - created_count),
        dry_run=dry_run,
    )


def build_snapshot_report(
    session: Session,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    snapshot_version: str | None = None,
) -> SnapshotReport:
    query = session.query(PaperRecommendationGroupSnapshot).options(
        joinedload(PaperRecommendationGroupSnapshot.representative_record)
    )
    if from_date is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.created_at >= from_date)
    if to_date is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.created_at <= to_date)
    if snapshot_version is not None:
        query = query.filter(PaperRecommendationGroupSnapshot.snapshot_version == snapshot_version)
    snapshots = query.order_by(
        PaperRecommendationGroupSnapshot.created_at.asc(),
        PaperRecommendationGroupSnapshot.id.asc(),
    ).all()
    return SnapshotReport(
        summary=_summarize_snapshots(snapshots),
        by_market_line_bucket=_group_snapshot_report(
            snapshots,
            lambda snapshot: f"{snapshot.market_type}:{snapshot.line_bucket or 'unknown'}",
        ),
        by_market_stake_bucket=_group_snapshot_report(
            snapshots,
            lambda snapshot: f"{snapshot.market_type}:{_format_decimal(snapshot.suggested_stake_units, STAKE_QUANT)}",
        ),
        by_snapshot_source=_group_snapshot_report(snapshots, lambda snapshot: snapshot.snapshot_source),
    )


def format_snapshot_report(report: SnapshotReport) -> str:
    lines = [
        "Paper recommendation group snapshot report",
        _format_report_group("summary", report.summary),
        "",
        "By market_type + line_bucket:",
    ]
    lines.extend(_format_report_groups(report.by_market_line_bucket))
    lines.extend(["", "By market_type + stake_bucket:"])
    lines.extend(_format_report_groups(report.by_market_stake_bucket))
    lines.extend(["", "By snapshot_source:"])
    lines.extend(_format_report_groups(report.by_snapshot_source))
    return "\n".join(lines)


def _snapshot_exists(
    session: Session,
    *,
    snapshot_source: str,
    snapshot_version: str,
    group_key: str,
    signal_record_ids_json: str,
) -> bool:
    return (
        session.query(PaperRecommendationGroupSnapshot)
        .filter(PaperRecommendationGroupSnapshot.snapshot_source == snapshot_source)
        .filter(PaperRecommendationGroupSnapshot.snapshot_version == snapshot_version)
        .filter(PaperRecommendationGroupSnapshot.group_key == group_key)
        .filter(PaperRecommendationGroupSnapshot.signal_record_ids_json == signal_record_ids_json)
        .first()
        is not None
    )


def _json_list(values) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def _line_bucket_for_group(
    records: list[PaperRecommendationRecord],
    representative_record_id: int,
) -> str | None:
    for record in records:
        if record.id == representative_record_id:
            return record.line_bucket
    return records[0].line_bucket if records else None


def _count_backfill_groups(
    session: Session,
    record_ids: list[int],
    *,
    snapshot_source: str,
    snapshot_version: str,
) -> _SnapshotBackfillCounts:
    if not record_ids:
        return _SnapshotBackfillCounts(
            candidate_group_count=0,
            creatable_group_count=0,
            existing_group_count=0,
        )
    record_id_set = set(record_ids)
    all_records = (
        session.query(PaperRecommendationRecord)
        .order_by(PaperRecommendationRecord.created_at.asc(), PaperRecommendationRecord.id.asc())
        .all()
    )
    workspace = build_paper_confidence_workspace(all_records)
    candidate_count = 0
    existing_count = 0
    for group in workspace.groups:
        if not record_id_set.intersection(group.signal_record_ids):
            continue
        candidate_count += 1
        signal_record_ids_json = _json_list(tuple(sorted(group.signal_record_ids)))
        if _snapshot_exists(
            session,
            snapshot_source=snapshot_source,
            snapshot_version=snapshot_version,
            group_key=group.group_key,
            signal_record_ids_json=signal_record_ids_json,
        ):
            existing_count += 1
            continue
    return _SnapshotBackfillCounts(
        candidate_group_count=candidate_count,
        creatable_group_count=candidate_count - existing_count,
        existing_group_count=existing_count,
    )


def _group_snapshot_report(
    snapshots: list[PaperRecommendationGroupSnapshot],
    key_func,
) -> dict[str, SnapshotReportGroup]:
    grouped: dict[str, list[PaperRecommendationGroupSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(key_func(snapshot), []).append(snapshot)
    return {
        name: _report_group_for_snapshots(name, group_snapshots)
        for name, group_snapshots in sorted(grouped.items(), key=lambda item: item[0])
    }


def _report_group_for_snapshots(
    name: str,
    snapshots: list[PaperRecommendationGroupSnapshot],
) -> SnapshotReportGroup:
    summary = _summarize_snapshots(snapshots)
    return SnapshotReportGroup(
        group_name=name,
        group_count=summary.group_count,
        settled_groups=summary.settled_groups,
        pending_groups=summary.pending_groups,
        suggested_stake_units=summary.suggested_stake_units,
        flat_profit_units=summary.flat_profit_units,
        weighted_profit_units=summary.weighted_profit_units,
        flat_roi=summary.flat_roi,
        weighted_roi=summary.weighted_roi,
    )


def _summarize_snapshots(snapshots: list[PaperRecommendationGroupSnapshot]) -> SnapshotReportSummary:
    settled = [snapshot for snapshot in snapshots if _snapshot_status(snapshot) == "settled"]
    pending = [snapshot for snapshot in snapshots if _snapshot_status(snapshot) == "pending"]
    total_stake = sum((_snapshot_stake(snapshot) for snapshot in settled), Decimal("0"))
    flat_profit = sum((_snapshot_flat_profit(snapshot) for snapshot in settled), Decimal("0"))
    weighted_profit = sum((_snapshot_weighted_profit(snapshot) for snapshot in settled), Decimal("0"))
    return SnapshotReportSummary(
        group_count=len(snapshots),
        settled_groups=len(settled),
        pending_groups=len(pending),
        suggested_stake_units=_quantize(total_stake, STAKE_QUANT),
        flat_profit_units=_quantize(flat_profit, MONEY_QUANT),
        weighted_profit_units=_quantize(weighted_profit, MONEY_QUANT),
        flat_roi=_ratio(flat_profit, Decimal(len(settled))) if settled else Decimal("0.0000"),
        weighted_roi=_ratio(weighted_profit, total_stake),
    )


def _snapshot_status(snapshot: PaperRecommendationGroupSnapshot) -> str:
    record = snapshot.representative_record
    if record is not None and record.status:
        return record.status
    return snapshot.status


def _snapshot_stake(snapshot: PaperRecommendationGroupSnapshot) -> Decimal:
    return Decimal(snapshot.suggested_stake_units or Decimal("0"))


def _snapshot_flat_profit(snapshot: PaperRecommendationGroupSnapshot) -> Decimal:
    record = snapshot.representative_record
    if record is not None and record.status == "settled" and record.profit_units is not None:
        return _quantize(record.profit_units, MONEY_QUANT)
    return _quantize(snapshot.flat_profit_units or Decimal("0"), MONEY_QUANT)


def _snapshot_weighted_profit(snapshot: PaperRecommendationGroupSnapshot) -> Decimal:
    return _quantize(_snapshot_flat_profit(snapshot) * _snapshot_stake(snapshot), MONEY_QUANT)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return _quantize(numerator / denominator, RATIO_QUANT)


def _quantize(value: Decimal, quant: Decimal) -> Decimal:
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def _format_report_groups(groups: dict[str, SnapshotReportGroup]) -> list[str]:
    if not groups:
        return ["- none"]
    return [_format_report_group(name, group) for name, group in groups.items()]


def _format_report_group(name: str, group: SnapshotReportGroup | SnapshotReportSummary) -> str:
    return (
        f"- {name}: groups={group.group_count}, settled={group.settled_groups}, "
        f"stake={_format_decimal(group.suggested_stake_units, STAKE_QUANT)}, "
        f"flat_profit={_format_decimal(group.flat_profit_units, MONEY_QUANT)}, "
        f"weighted_profit={_format_decimal(group.weighted_profit_units, MONEY_QUANT)}, "
        f"weighted_roi={_format_decimal(group.weighted_roi, RATIO_QUANT)}"
    )


def _format_decimal(value: Decimal, quant: Decimal) -> str:
    return str(_quantize(value, quant))

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

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


@dataclass(frozen=True)
class CreatedPaperGroupSnapshot:
    snapshot: PaperRecommendationGroupSnapshot
    group: PaperConfidenceGroup


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
        signal_record_ids_json = _json_list(signal_record_ids)
        duplicate = (
            session.query(PaperRecommendationGroupSnapshot)
            .filter(PaperRecommendationGroupSnapshot.snapshot_source == snapshot_source)
            .filter(PaperRecommendationGroupSnapshot.snapshot_version == snapshot_version)
            .filter(PaperRecommendationGroupSnapshot.group_key == group.group_key)
            .filter(PaperRecommendationGroupSnapshot.signal_record_ids_json == signal_record_ids_json)
            .first()
        )
        if duplicate is not None:
            continue
        group_records = [
            record
            for record in all_records
            if record.id in set(signal_record_ids)
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
        session.add(snapshot)
        session.flush()
        created.append(CreatedPaperGroupSnapshot(snapshot=snapshot, group=group))
    session.commit()
    return created


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

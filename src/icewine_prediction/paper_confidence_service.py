from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from icewine_prediction.models import PaperRecommendationRecord


DECIMAL_ZERO = Decimal("0")
MONEY_QUANT = Decimal("0.001")
RATIO_QUANT = Decimal("0.0000")
STAKE_QUANT = Decimal("0.00")


@dataclass(frozen=True)
class PaperConfidenceGroup:
    group_key: str
    match_id: int
    source_match_id: str | None
    kickoff_time: object
    league_name: str
    league_display_name: str | None
    home_team_name: str
    home_team_display_name: str | None
    home_team_logo_url: str | None
    home_score: int | None
    away_team_name: str
    away_team_display_name: str | None
    away_team_logo_url: str | None
    away_score: int | None
    market_type: str
    logical_side: str
    recommendation_text: str | None
    representative_record_id: int
    representative_strategy_key: str
    representative_market_line: Decimal
    representative_odds: Decimal
    signal_record_ids: tuple[int, ...]
    triggered_strategy_keys: tuple[str, ...]
    triggered_strategy_display_names: tuple[str, ...]
    signal_families: tuple[str, ...]
    confidence_score: int
    suggested_stake_units: Decimal
    stake_cap_reason: str
    status: str
    settlement_result: str | None
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    warning: str | None = None


@dataclass(frozen=True)
class PaperConfidenceGroupSummary:
    group_name: str
    group_count: int
    settled_groups: int
    suggested_stake_units: Decimal
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class PaperConfidenceSummary:
    group_count: int
    settled_groups: int
    suggested_stake_units: Decimal
    flat_profit_units: Decimal
    weighted_profit_units: Decimal
    flat_roi: Decimal
    weighted_roi: Decimal


@dataclass(frozen=True)
class PaperConfidenceWorkspace:
    summary: PaperConfidenceSummary
    groups: list[PaperConfidenceGroup]
    by_score_bucket: list[PaperConfidenceGroupSummary]
    by_stake_bucket: list[PaperConfidenceGroupSummary]
    by_family_combo: list[PaperConfidenceGroupSummary]


def build_paper_confidence_workspace(
    records: list[PaperRecommendationRecord],
) -> PaperConfidenceWorkspace:
    groups = [
        _build_group(group_records)
        for group_records in _same_direction_groups(records).values()
        if group_records
    ]
    groups.sort(key=lambda group: (str(group.kickoff_time), group.match_id, group.market_type, group.logical_side))
    return PaperConfidenceWorkspace(
        summary=_summarize(groups),
        groups=groups,
        by_score_bucket=_group_summaries(groups, _score_bucket),
        by_stake_bucket=_group_summaries(groups, lambda group: str(group.suggested_stake_units)),
        by_family_combo=_group_summaries(groups, lambda group: "+".join(group.signal_families) or "unknown"),
    )


def strategy_family(strategy_key: str) -> str:
    mapping = {
        "asian_away_cover_hgb_edge_v1": "asian_away_hgb",
        "asian_away_cover_hgb_bucket_v2": "asian_away_hgb",
        "asian_home_cover_hgb_favorite_bucket_v1": "asian_home_hgb",
        "total_goals_hgb_bucket_v2": "total_goals_hgb",
        "total_goals_hgb_low_line_bucket_v3": "total_goals_hgb",
    }
    return mapping.get(strategy_key, "unknown")


def stake_for_score(score: int) -> Decimal:
    if score < 55:
        return Decimal("0.00")
    if score < 60:
        return Decimal("0.50")
    if score < 65:
        return Decimal("0.75")
    if score < 70:
        return Decimal("1.00")
    if score < 75:
        return Decimal("1.25")
    if score < 80:
        return Decimal("1.50")
    if score < 85:
        return Decimal("1.75")
    if score < 90:
        return Decimal("2.00")
    if score < 95:
        return Decimal("2.50")
    return Decimal("3.00")


def confidence_score_for_group(
    records: list[PaperRecommendationRecord],
    representative: PaperRecommendationRecord,
) -> tuple[int, Decimal, str]:
    families = {strategy_family(record.strategy_key) for record in records}
    edge = _score_edge_for_group(records, representative)
    score = Decimal("50") + min(edge * Decimal("100"), Decimal("30"))
    if len(families) > 1:
        score += Decimal("8")
    if any(_is_bucket_strategy(record.strategy_key) for record in records):
        score += Decimal("8")
    if any(_has_risk_tag(record, "model_consensus:confirmed") for record in records):
        score += Decimal("5")
    if len(records) > len(families):
        score -= Decimal("3")
    if any(record.is_manually_adjusted for record in records):
        score -= Decimal("5")
    score_int = max(0, min(100, int(score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))))
    stake = stake_for_score(score_int)
    cap_reason = "none"
    if len(families) == 1 and len(records) > 1 and stake > Decimal("1.25"):
        stake = Decimal("1.25")
        cap_reason = "same_family_cap"
    elif len(families) == 1 and stake > Decimal("1.00"):
        stake = Decimal("1.00")
        cap_reason = "single_family_limited_history"
    return score_int, stake, cap_reason


def _same_direction_groups(
    records: list[PaperRecommendationRecord],
) -> dict[tuple[int, str, str], list[PaperRecommendationRecord]]:
    active_records = [record for record in records if record.status != "void"]
    grouped: dict[tuple[int, str, str], list[PaperRecommendationRecord]] = {}
    for record in active_records:
        key = (record.match_id, record.market_type, record.side)
        grouped.setdefault(key, []).append(record)
    return grouped


def _build_group(records: list[PaperRecommendationRecord]) -> PaperConfidenceGroup:
    representative = _select_representative(records)
    score, stake, cap_reason = confidence_score_for_group(records, representative)
    flat_profit = _flat_profit(representative)
    weighted_profit = _quantize_money(flat_profit * stake)
    family_names = tuple(sorted({strategy_family(record.strategy_key) for record in records}))
    settlement_results = {record.settlement_result for record in records if record.settlement_result}
    warning = None
    if len(settlement_results) > 1:
        warning = "settlement_result_mismatch"
    return PaperConfidenceGroup(
        group_key=f"{representative.match_id}:{representative.market_type}:{representative.side}",
        match_id=representative.match_id,
        source_match_id=representative.source_match_id,
        kickoff_time=representative.kickoff_time,
        league_name=representative.league_name,
        league_display_name=representative.league_display_name,
        home_team_name=representative.home_team_name,
        home_team_display_name=representative.home_team_display_name,
        home_team_logo_url=representative.match.home_team.logo_url if representative.match else None,
        home_score=representative.match.home_score if representative.match else None,
        away_team_name=representative.away_team_name,
        away_team_display_name=representative.away_team_display_name,
        away_team_logo_url=representative.match.away_team.logo_url if representative.match else None,
        away_score=representative.match.away_score if representative.match else None,
        market_type=representative.market_type,
        logical_side=representative.side,
        recommendation_text=representative.recommended_handicap,
        representative_record_id=representative.id,
        representative_strategy_key=representative.strategy_key,
        representative_market_line=representative.current_market_line,
        representative_odds=representative.current_odds,
        signal_record_ids=tuple(record.id for record in sorted(records, key=lambda item: item.id)),
        triggered_strategy_keys=tuple(record.strategy_key for record in sorted(records, key=lambda item: item.id)),
        triggered_strategy_display_names=tuple(
            record.strategy_display_name for record in sorted(records, key=lambda item: item.id)
        ),
        signal_families=family_names,
        confidence_score=score,
        suggested_stake_units=stake.quantize(STAKE_QUANT),
        stake_cap_reason=cap_reason,
        status=_group_status(records),
        settlement_result=representative.settlement_result,
        flat_profit_units=flat_profit,
        weighted_profit_units=weighted_profit,
        warning=warning,
    )


def _select_representative(records: list[PaperRecommendationRecord]) -> PaperRecommendationRecord:
    return sorted(records, key=_representative_sort_key, reverse=True)[0]


def _representative_sort_key(record: PaperRecommendationRecord) -> tuple:
    return (
        record.status != "void",
        record.current_market_line is not None and record.current_odds is not None,
        _strategy_priority(record.strategy_key),
        record.edge or Decimal("0"),
        _model_margin(record),
        record.created_at,
        record.id,
    )


def _strategy_priority(strategy_key: str) -> int:
    if _is_bucket_strategy(strategy_key):
        return 2
    if strategy_key.endswith("_v1"):
        return 1
    return 0


def _is_bucket_strategy(strategy_key: str) -> bool:
    return "bucket" in strategy_key


def _score_edge_for_group(
    records: list[PaperRecommendationRecord],
    representative: PaperRecommendationRecord,
) -> Decimal:
    edges = [_score_edge_contribution(record) for record in records]
    return max(edges) if edges else (representative.edge or Decimal("0"))


def _score_edge_contribution(record: PaperRecommendationRecord) -> Decimal:
    edge = record.edge or Decimal("0")
    if record.strategy_key == "total_goals_hgb_low_line_bucket_v3":
        return min(edge, Decimal("0.0100"))
    return edge


def _has_risk_tag(record: PaperRecommendationRecord, tag: str) -> bool:
    return tag in {item.strip() for item in (record.risk_tags or "").split(",") if item.strip()}


def _model_margin(record: PaperRecommendationRecord) -> Decimal:
    if record.model_probability is None or record.market_probability is None:
        return Decimal("0")
    return record.model_probability - record.market_probability


def _group_status(records: list[PaperRecommendationRecord]) -> str:
    statuses = {record.status for record in records}
    if "pending" in statuses:
        return "pending"
    if "unsettleable" in statuses:
        return "unsettleable"
    if statuses == {"void"}:
        return "void"
    if "settled" in statuses:
        return "settled"
    return sorted(statuses)[0] if statuses else "unknown"


def _flat_profit(record: PaperRecommendationRecord) -> Decimal:
    if record.status != "settled" or record.profit_units is None:
        return Decimal("0.000")
    return _quantize_money(record.profit_units)


def _summarize(groups: list[PaperConfidenceGroup]) -> PaperConfidenceSummary:
    settled = [group for group in groups if group.status == "settled"]
    total_stake = sum((group.suggested_stake_units for group in settled), Decimal("0"))
    flat_profit = sum((group.flat_profit_units for group in settled), Decimal("0"))
    weighted_profit = sum((group.weighted_profit_units for group in settled), Decimal("0"))
    return PaperConfidenceSummary(
        group_count=len(groups),
        settled_groups=len(settled),
        suggested_stake_units=total_stake.quantize(STAKE_QUANT),
        flat_profit_units=_quantize_money(flat_profit),
        weighted_profit_units=_quantize_money(weighted_profit),
        flat_roi=_ratio(flat_profit, Decimal(len(settled))) if settled else Decimal("0.0000"),
        weighted_roi=_ratio(weighted_profit, total_stake),
    )


def _group_summaries(
    groups: list[PaperConfidenceGroup],
    key_func,
) -> list[PaperConfidenceGroupSummary]:
    grouped: dict[str, list[PaperConfidenceGroup]] = {}
    for group in groups:
        grouped.setdefault(key_func(group), []).append(group)
    return [
        _summary_for_group(name, group_items)
        for name, group_items in sorted(grouped.items(), key=lambda item: item[0])
    ]


def _summary_for_group(
    name: str,
    groups: list[PaperConfidenceGroup],
) -> PaperConfidenceGroupSummary:
    summary = _summarize(groups)
    return PaperConfidenceGroupSummary(
        group_name=name,
        group_count=summary.group_count,
        settled_groups=summary.settled_groups,
        suggested_stake_units=summary.suggested_stake_units,
        flat_profit_units=summary.flat_profit_units,
        weighted_profit_units=summary.weighted_profit_units,
        flat_roi=summary.flat_roi,
        weighted_roi=summary.weighted_roi,
    )


def _score_bucket(group: PaperConfidenceGroup) -> str:
    score = group.confidence_score
    if score < 55:
        return "<55"
    if score >= 95:
        return "95+"
    lower = ((score - 55) // 5) * 5 + 55
    return f"{lower}-{lower + 4}"


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / denominator).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

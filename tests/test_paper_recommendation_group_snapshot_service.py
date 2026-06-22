from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from icewine_prediction.models import (
    League,
    Match,
    PaperRecommendationGroupSnapshot,
    PaperRecommendationRecord,
    Team,
)


BEIJING = ZoneInfo("Asia/Shanghai")


def test_snapshot_model_can_be_inserted(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    snapshot = PaperRecommendationGroupSnapshot(
        created_at=_now(),
        snapshot_source="manual_record",
        snapshot_version="paper_confidence_v1",
        group_key=f"{match.id}:asian_handicap:away_cover",
        match_id=match.id,
        market_type="asian_handicap",
        side="away_cover",
        representative_record_id=record.id,
        signal_record_ids_json=json.dumps([record.id]),
        triggered_strategy_keys_json=json.dumps([record.strategy_key]),
        triggered_strategy_display_names_json=json.dumps([record.strategy_display_name]),
        signal_families_json=json.dumps(["asian_away_hgb"]),
        confidence_score=60,
        suggested_stake_units=Decimal("0.75"),
        stake_cap_reason="single_family_limited_history",
        recommendation_text="客队 +0.50",
        representative_market_line=Decimal("-0.50"),
        representative_odds=Decimal("1.930"),
        line_bucket="away_underdog",
        status="pending",
        settlement_result=None,
        flat_profit_units=Decimal("0.000"),
        weighted_profit_units=Decimal("0.000"),
        is_backfilled=False,
        source_record_created_at_min=record.created_at,
        source_record_created_at_max=record.created_at,
    )

    session.add(snapshot)
    session.commit()

    loaded = session.get(PaperRecommendationGroupSnapshot, snapshot.id)
    assert loaded is not None
    assert loaded.group_key == f"{match.id}:asian_handicap:away_cover"
    assert loaded.suggested_stake_units == Decimal("0.75")
    assert loaded.line_bucket == "away_underdog"


def test_snapshot_identity_is_unique(session):
    match = _seed_match(session)
    record = _paper_record(session, match)
    session.add(_snapshot(match, record))
    session.commit()

    session.add(_snapshot(match, record))

    with pytest.raises(IntegrityError):
        session.commit()


def _now() -> datetime:
    return datetime(2026, 6, 22, 18, 0, tzinfo=BEIJING)


def _seed_match(session, *, home_score=None, away_score=None, status="scheduled") -> Match:
    league = League(
        source_name="api-football",
        source_league_id="98",
        name="J1 League",
        country_or_region="Japan",
        is_enabled=True,
    )
    home = Team(source_name="api-football", source_team_id="1", canonical_name="Yokohama F. Marinos")
    away = Team(source_name="api-football", source_team_id="2", canonical_name="Vissel Kobe")
    match = Match(
        source_name="api-football",
        source_match_id="fixture-1",
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 6, 22, 19, 0, tzinfo=BEIJING),
        status=status,
        home_score=home_score,
        away_score=away_score,
        season=2026,
    )
    session.add_all([league, home, away, match])
    session.commit()
    return match


def _paper_record(session, match: Match, **overrides) -> PaperRecommendationRecord:
    values = {
        "match_id": match.id,
        "source_match_id": match.source_match_id,
        "created_at": _now(),
        "updated_at": _now(),
        "league_name": match.league.name,
        "league_display_name": "日职联",
        "home_team_name": match.home_team.canonical_name,
        "home_team_display_name": "横滨水手",
        "away_team_name": match.away_team.canonical_name,
        "away_team_display_name": "神户胜利船",
        "kickoff_time": match.kickoff_time,
        "strategy_key": "asian_away_cover_hgb_edge_v1",
        "strategy_display_name": "亚盘客队方向 HGB edge v1",
        "model_name": "hgb",
        "signal_version": "v1",
        "market_type": "asian_handicap",
        "side": "away_cover",
        "recommended_handicap": "客队 +0.50",
        "original_recommended_handicap": "客队 +0.50",
        "line_bucket": "away_underdog",
        "risk_tags": "line_bucket:away_underdog",
        "original_market_line": Decimal("-0.50"),
        "original_odds": Decimal("1.930"),
        "current_market_line": Decimal("-0.50"),
        "current_odds": Decimal("1.930"),
        "model_probability": Decimal("0.5600"),
        "market_probability": Decimal("0.5100"),
        "edge": Decimal("0.1000"),
        "scoring_edge": Decimal("0.1000"),
        "stake_units": Decimal("1.00"),
        "status": "pending",
        "is_manually_adjusted": False,
    }
    values.update(overrides)
    record = PaperRecommendationRecord(**values)
    session.add(record)
    session.commit()
    return record


def _snapshot(match: Match, record: PaperRecommendationRecord) -> PaperRecommendationGroupSnapshot:
    return PaperRecommendationGroupSnapshot(
        created_at=_now(),
        snapshot_source="manual_record",
        snapshot_version="paper_confidence_v1",
        group_key=f"{match.id}:asian_handicap:away_cover",
        match_id=match.id,
        market_type="asian_handicap",
        side="away_cover",
        representative_record_id=record.id,
        signal_record_ids_json=json.dumps([record.id]),
        triggered_strategy_keys_json=json.dumps([record.strategy_key]),
        triggered_strategy_display_names_json=json.dumps([record.strategy_display_name]),
        signal_families_json=json.dumps(["asian_away_hgb"]),
        confidence_score=60,
        suggested_stake_units=Decimal("0.75"),
        stake_cap_reason="single_family_limited_history",
        recommendation_text="客队 +0.50",
        representative_market_line=Decimal("-0.50"),
        representative_odds=Decimal("1.930"),
        line_bucket="away_underdog",
        status="pending",
        settlement_result=None,
        flat_profit_units=Decimal("0.000"),
        weighted_profit_units=Decimal("0.000"),
        is_backfilled=False,
        source_record_created_at_min=record.created_at,
        source_record_created_at_max=record.created_at,
    )

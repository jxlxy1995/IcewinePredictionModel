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
from icewine_prediction.paper_recommendation_group_snapshot_service import (
    PAPER_CONFIDENCE_SNAPSHOT_VERSION,
    create_group_snapshots_for_record_ids,
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


def test_create_group_snapshots_groups_same_match_market_and_side(session):
    match = _seed_match(session)
    first = _paper_record(session, match, edge=Decimal("0.1200"), scoring_edge=Decimal("0.1200"))
    second = _paper_record(
        session,
        match,
        strategy_key="asian_away_cover_hgb_bucket_v2",
        strategy_display_name="亚盘客队方向 HGB bucket v2",
        signal_version="v2",
        risk_tags="line_bucket:away_underdog,strategy:bucket_v2",
        edge=Decimal("0.2200"),
        scoring_edge=Decimal("0.2200"),
    )

    results = create_group_snapshots_for_record_ids(
        session,
        [first.id, second.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )

    assert len(results) == 1
    snapshot = results[0].snapshot
    assert snapshot.snapshot_version == PAPER_CONFIDENCE_SNAPSHOT_VERSION
    assert snapshot.snapshot_source == "manual_record"
    assert snapshot.group_key == f"{match.id}:asian_handicap:away_cover"
    assert json.loads(snapshot.signal_record_ids_json) == [first.id, second.id]
    assert json.loads(snapshot.triggered_strategy_keys_json) == [
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    ]
    assert snapshot.confidence_score >= 70
    assert snapshot.suggested_stake_units >= Decimal("1.00")
    assert snapshot.line_bucket == "away_underdog"


def test_create_group_snapshots_keeps_different_markets_separate(session):
    match = _seed_match(session)
    asian = _paper_record(session, match)
    total = _paper_record(
        session,
        match,
        strategy_key="total_goals_hgb_bucket_v2",
        strategy_display_name="大小球 HGB bucket v2",
        model_name="hgb_total_goals",
        market_type="total_goals",
        side="under",
        recommended_handicap="小 2.50",
        original_recommended_handicap="小 2.50",
        line_bucket="mid_2.50",
        risk_tags="line_bucket:mid_2.50,strategy:total_goals_bucket_v2",
        original_market_line=Decimal("2.50"),
        current_market_line=Decimal("2.50"),
        edge=Decimal("0.1300"),
        scoring_edge=Decimal("0.1300"),
    )

    results = create_group_snapshots_for_record_ids(
        session,
        [asian.id, total.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )

    assert sorted(result.snapshot.market_type for result in results) == [
        "asian_handicap",
        "total_goals",
    ]
    assert sorted(result.snapshot.line_bucket for result in results) == [
        "away_underdog",
        "mid_2.50",
    ]


def test_create_group_snapshots_is_idempotent_per_source_version_group_and_signal_set(session):
    match = _seed_match(session)
    record = _paper_record(session, match)

    first = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    second = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    third = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        snapshot_version="paper_confidence_v2",
        created_at=_now(),
    )

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def test_create_group_snapshots_treats_unique_constraint_race_as_duplicate(session, monkeypatch):
    match = _seed_match(session)
    record = _paper_record(session, match)
    first = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )
    original_query = session.query
    snapshot_query_misses_remaining = 1

    class SnapshotQueryMiss:
        def __init__(self, query):
            self._query = query

        def __getattr__(self, name):
            return getattr(self._query, name)

        def filter(self, *criteria):
            self._query = self._query.filter(*criteria)
            return self

        def first(self):
            return None

    def query_with_stale_snapshot_read(*entities, **kwargs):
        nonlocal snapshot_query_misses_remaining
        query = original_query(*entities, **kwargs)
        if entities and entities[0] is PaperRecommendationGroupSnapshot and snapshot_query_misses_remaining:
            snapshot_query_misses_remaining -= 1
            return SnapshotQueryMiss(query)
        return query

    monkeypatch.setattr(session, "query", query_with_stale_snapshot_read)

    second = create_group_snapshots_for_record_ids(
        session,
        [record.id],
        snapshot_source="manual_record",
        created_at=_now(),
    )

    assert len(first) == 1
    assert second == []
    assert original_query(PaperRecommendationGroupSnapshot).count() == 1


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

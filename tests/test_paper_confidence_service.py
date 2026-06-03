from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, PaperRecommendationRecord, Team
from icewine_prediction.paper_confidence_service import (
    build_paper_confidence_workspace,
    stake_for_score,
    strategy_family,
)
from icewine_prediction.paper_recommendation_queue_service import PaperQueueRow
from icewine_prediction.paper_recommendation_tracking_service import (
    ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    create_paper_record_from_queue_row,
    settle_paper_records,
    void_paper_record,
)


def test_build_paper_confidence_workspace_groups_same_direction_strategy_records(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50"), edge=Decimal("0.1400")),
        recorded_at=_now(),
    )
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            line=Decimal("-0.50"),
            edge=Decimal("0.2200"),
            strategy_key="asian_away_cover_hgb_bucket_v2",
            strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
            signal_version="v2",
            risk_tags=("line_bucket:away_underdog", "strategy:bucket_v2"),
        ),
        recorded_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    workspace = build_paper_confidence_workspace(
        session.query(PaperRecommendationRecord).order_by(PaperRecommendationRecord.id).all()
    )

    assert workspace.summary.group_count == 1
    group = workspace.groups[0]
    assert group.match_id == match.id
    assert group.market_type == "asian_handicap"
    assert group.logical_side == "away_cover"
    assert group.triggered_strategy_keys == (
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    )
    assert len(group.signal_record_ids) == 2
    assert group.signal_families == ("asian_away_hgb",)
    assert group.representative_strategy_key == "asian_away_cover_hgb_bucket_v2"
    assert group.flat_profit_units == Decimal("0.930")
    assert group.weighted_profit_units == Decimal("1.163")
    assert workspace.summary.flat_profit_units == Decimal("0.930")


def test_build_paper_confidence_workspace_exposes_match_display_fields(session):
    match = _seed_match(session, home_score=2, away_score=1, status="finished")
    match.home_team.logo_url = "https://img.example/home.png"
    match.away_team.logo_url = "https://img.example/away.png"
    session.commit()
    create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    group = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all()).groups[0]

    assert group.home_team_logo_url == "https://img.example/home.png"
    assert group.away_team_logo_url == "https://img.example/away.png"
    assert group.home_score == 2
    assert group.away_score == 1


def test_build_paper_confidence_workspace_excludes_void_only_records(session):
    match = _seed_match(session)
    record = create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )
    void_paper_record(session, record.id)

    workspace = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all())

    assert workspace.summary.group_count == 0
    assert workspace.groups == []


def test_build_paper_confidence_workspace_keeps_different_markets_separate(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            market_type="total_goals",
            side="under",
            recommended_handicap="小 2.75",
            line=Decimal("2.75"),
            odds=Decimal("2.000"),
            edge=Decimal("0.1100"),
            line_bucket="mid_2.75",
            risk_tags=("line_bucket:mid_2.75", "strategy:total_goals_bucket_v2"),
            strategy_key="total_goals_hgb_bucket_v2",
            strategy_display_name="大小球方向 · HGB分盘口桶 v2",
            signal_version="v2",
        ),
        recorded_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    workspace = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all())

    assert {(group.market_type, group.logical_side) for group in workspace.groups} == {
        ("asian_handicap", "away_cover"),
        ("total_goals", "under"),
    }


def test_representative_record_prefers_bucket_signal_and_higher_edge(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50"), edge=Decimal("0.2100")),
        recorded_at=_now(),
    )
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            line=Decimal("-0.25"),
            odds=Decimal("1.850"),
            edge=Decimal("0.1500"),
            strategy_key="asian_away_cover_hgb_bucket_v2",
            strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
            signal_version="v2",
            risk_tags=("line_bucket:away_underdog", "strategy:bucket_v2"),
        ),
        recorded_at=_now(),
    )

    workspace = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all())

    group = workspace.groups[0]
    assert group.representative_strategy_key == "asian_away_cover_hgb_bucket_v2"
    assert group.representative_market_line == Decimal("-0.25")
    assert group.representative_odds == Decimal("1.850")


def test_confidence_stake_caps_same_family_support(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50"), edge=Decimal("0.2600")),
        recorded_at=_now(),
    )
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            line=Decimal("-0.50"),
            edge=Decimal("0.2800"),
            strategy_key="asian_away_cover_hgb_bucket_v2",
            strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
            signal_version="v2",
            risk_tags=("line_bucket:away_underdog", "strategy:bucket_v2"),
        ),
        recorded_at=_now(),
    )

    group = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all()).groups[0]

    assert group.confidence_score >= 75
    assert group.suggested_stake_units == Decimal("1.25")
    assert group.stake_cap_reason == "same_family_cap"


def test_confidence_score_boosts_model_consensus_confirmed_support(session):
    plain_match = _seed_match(session)
    confirmed_match = Match(
        league=plain_match.league,
        home_team=plain_match.home_team,
        away_team=plain_match.away_team,
        kickoff_time=datetime(2026, 5, 31, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="scheduled",
        source_name="api_football",
        source_match_id="17447",
    )
    session.add(confirmed_match)
    session.commit()
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            plain_match,
            status="candidate",
            line=Decimal("-0.50"),
            side="home_cover",
            recommended_handicap="主队 -0.50",
            edge=Decimal("0.1500"),
            line_bucket="home_favorite",
            risk_tags=("line_bucket:home_favorite", "strategy:asian_home_favorite_bucket_v1"),
            strategy_key="asian_home_cover_hgb_favorite_bucket_v1",
            strategy_display_name="亚盘主队让球方向 · HGB分盘口桶 v1",
        ),
        recorded_at=_now(),
    )
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            confirmed_match,
            status="candidate",
            line=Decimal("-0.50"),
            side="home_cover",
            recommended_handicap="主队 -0.50",
            edge=Decimal("0.1500"),
            line_bucket="home_favorite",
            risk_tags=(
                "line_bucket:home_favorite",
                "model_consensus:confirmed",
                "strategy:asian_home_favorite_bucket_v1",
            ),
            strategy_key="asian_home_cover_hgb_favorite_bucket_v1",
            strategy_display_name="亚盘主队让球方向 · HGB分盘口桶 v1",
        ),
        recorded_at=_now(),
    )

    groups = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all()).groups
    group_by_match_id = {group.match_id: group for group in groups}

    assert (
        group_by_match_id[confirmed_match.id].confidence_score
        > group_by_match_id[plain_match.id].confidence_score
    )
    assert group_by_match_id[confirmed_match.id].suggested_stake_units >= Decimal("1.00")


def test_stake_for_score_uses_quarter_unit_steps():
    assert stake_for_score(54) == Decimal("0.00")
    assert stake_for_score(55) == Decimal("0.50")
    assert stake_for_score(60) == Decimal("0.75")
    assert stake_for_score(65) == Decimal("1.00")
    assert stake_for_score(70) == Decimal("1.25")
    assert stake_for_score(75) == Decimal("1.50")
    assert stake_for_score(80) == Decimal("1.75")
    assert stake_for_score(85) == Decimal("2.00")
    assert stake_for_score(90) == Decimal("2.50")
    assert stake_for_score(95) == Decimal("3.00")


def test_strategy_family_maps_known_signals():
    assert strategy_family("asian_away_cover_hgb_edge_v1") == "asian_away_hgb"
    assert strategy_family("asian_away_cover_hgb_bucket_v2") == "asian_away_hgb"
    assert strategy_family("asian_home_cover_hgb_favorite_bucket_v1") == "asian_home_hgb"
    assert strategy_family("total_goals_hgb_bucket_v2") == "total_goals_hgb"
    assert strategy_family("total_goals_hgb_low_line_bucket_v3") == "total_goals_hgb"
    assert strategy_family("total_goals_hgb_confirmed_under_mid_275_v1") == "total_goals_hgb"
    assert strategy_family("new_signal") == "unknown"


def _seed_match(
    session,
    *,
    home_score: int | None = None,
    away_score: int | None = None,
    status: str = "scheduled",
) -> Match:
    league = League(name="Premier Division", country_or_region="Ireland", level=1)
    home = Team(canonical_name="Drogheda United")
    away = Team(canonical_name="Waterford")
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
        status=status,
        home_score=home_score,
        away_score=away_score,
        source_name="api_football",
        source_match_id="17446",
    )
    session.add_all([league, home, away, match])
    session.commit()
    return match


def _queue_row(
    match: Match,
    *,
    status: str,
    line: Decimal,
    market_type: str = "asian_handicap",
    side: str = "away_cover",
    recommended_handicap: str = "客队 +0.50",
    odds: Decimal = Decimal("1.930"),
    edge: Decimal = Decimal("0.1164"),
    line_bucket: str = "away_underdog",
    risk_tags: tuple[str, ...] = ("line_bucket:away_underdog",),
    strategy_key: str = ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    strategy_display_name: str = ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    signal_version: str = "v1",
) -> PaperQueueRow:
    market_probability = Decimal("0.5000")
    return PaperQueueRow(
        match_id=match.id,
        source_match_id=match.source_match_id,
        kickoff_time="2026-05-30T02:45:00+08:00",
        league_name=match.league.name,
        league_display_name="爱超",
        home_team_name=match.home_team.canonical_name,
        home_team_display_name="德罗赫达联",
        away_team_name=match.away_team.canonical_name,
        away_team_display_name="沃特福德联",
        status=status,
        market_type=market_type,
        line=line,
        side=side,
        recommended_handicap=recommended_handicap,
        odds=odds,
        model_probability=market_probability + edge,
        market_probability=market_probability,
        edge=edge,
        line_bucket=line_bucket,
        risk_tags=risk_tags,
        strategy_key=strategy_key,
        strategy_display_name=strategy_display_name,
        signal_version=signal_version,
    )


def _now() -> datetime:
    return datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

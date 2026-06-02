from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from icewine_prediction.models import League, Match, Team
from icewine_prediction.paper_recommendation_queue_service import PaperQueueRow
from icewine_prediction.paper_recommendation_tracking_service import (
    ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
    ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME,
    backfill_paper_record_from_candidate,
    build_paper_tracking_workspace,
    create_paper_record_from_queue_row,
    edit_paper_record,
    settle_paper_records,
    void_paper_record,
)


def test_create_paper_record_from_valid_candidate_locks_original_market(session):
    match = _seed_match(session)
    row = _queue_row(match, status="candidate", line=Decimal("-0.50"))

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.match_id == match.id
    assert record.strategy_key == ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY
    assert record.strategy_display_name == ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME
    assert record.market_type == "asian_handicap"
    assert record.side == "away_cover"
    assert record.recommended_handicap == "客队 +0.50"
    assert record.original_market_line == Decimal("-0.50")
    assert record.current_market_line == Decimal("-0.50")
    assert record.original_odds == Decimal("1.930")
    assert record.current_odds == Decimal("1.930")
    assert record.status == "pending"
    assert record.stake_units == Decimal("1.00")
    assert record.is_manually_adjusted is False


def test_create_paper_record_from_v2_candidate_preserves_strategy(session):
    match = _seed_match(session)
    row = _queue_row(
        match,
        status="candidate",
        line=Decimal("-0.50"),
        strategy_key="asian_away_cover_hgb_bucket_v2",
        strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
        signal_version="v2",
    )

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.strategy_key == "asian_away_cover_hgb_bucket_v2"
    assert record.strategy_display_name == "亚盘客队方向 · HGB分盘口桶 v2"
    assert record.signal_version == "v2"


def test_create_paper_record_from_home_favorite_candidate_preserves_strategy(session):
    match = _seed_match(session)
    row = _queue_row(
        match,
        status="candidate",
        line=Decimal("-0.50"),
        market_type="asian_handicap",
        side="home_cover",
        recommended_handicap="主队 -0.50",
        odds=Decimal("1.950"),
        edge=Decimal("0.1500"),
        line_bucket="home_favorite",
        risk_tags=("line_bucket:home_favorite", "strategy:asian_home_favorite_bucket_v1"),
        strategy_key=ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY,
        strategy_display_name=ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME,
        signal_version="v1",
    )

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.strategy_key == ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_KEY
    assert record.strategy_display_name == ASIAN_HOME_COVER_HGB_FAVORITE_BUCKET_V1_NAME
    assert record.market_type == "asian_handicap"
    assert record.side == "home_cover"
    assert record.recommended_handicap == "主队 -0.50"
    assert record.line_bucket == "home_favorite"
    assert record.signal_version == "v1"


def test_create_paper_record_from_total_goals_bucket_candidate_preserves_strategy(session):
    match = _seed_match(session)
    row = _queue_row(
        match,
        status="candidate",
        line=Decimal("2.75"),
        market_type="total_goals",
        side="under",
        recommended_handicap="小 2.75",
        odds=Decimal("2.000"),
        line_bucket="mid_2.75",
        risk_tags=("line_bucket:mid_2.75", "strategy:total_goals_bucket_v2"),
        strategy_key="total_goals_hgb_bucket_v2",
        strategy_display_name="大小球方向 · HGB分盘口桶 v2",
        signal_version="v2",
    )

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.strategy_key == "total_goals_hgb_bucket_v2"
    assert record.strategy_display_name == "大小球方向 · HGB分盘口桶 v2"
    assert record.market_type == "total_goals"
    assert record.side == "under"
    assert record.recommended_handicap == "小 2.75"
    assert record.current_market_line == Decimal("2.75")
    assert record.current_odds == Decimal("2.000")
    assert record.signal_version == "v2"


def test_create_paper_record_from_total_goals_low_line_v3_candidate_preserves_strategy(session):
    match = _seed_match(session)
    row = _queue_row(
        match,
        status="candidate",
        line=Decimal("2.25"),
        market_type="total_goals",
        side="over",
        recommended_handicap="澶?2.25",
        odds=Decimal("1.900"),
        line_bucket="low_<=2.25",
        risk_tags=("line_bucket:low_<=2.25", "strategy:total_goals_low_line_bucket_v3"),
        strategy_key="total_goals_hgb_low_line_bucket_v3",
        strategy_display_name="澶у皬鐞冧綆鐩樺彛鏂瑰悜 路 HGB鍒嗙洏鍙ｆ《 v3",
        signal_version="v3",
    )

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.strategy_key == "total_goals_hgb_low_line_bucket_v3"
    assert record.market_type == "total_goals"
    assert record.side == "over"
    assert record.line_bucket == "low_<=2.25"
    assert record.signal_version == "v3"


def test_create_paper_record_from_total_goals_confirmed_candidate_preserves_strategy(session):
    match = _seed_match(session)
    row = _queue_row(
        match,
        status="candidate",
        line=Decimal("2.75"),
        market_type="total_goals",
        side="under",
        recommended_handicap="小 2.75",
        odds=Decimal("2.000"),
        edge=Decimal("0.1500"),
        line_bucket="mid_2.75",
        risk_tags=(
            "line_bucket:mid_2.75",
            "model_consensus:confirmed",
            "strategy:total_goals_confirmed_under_mid_275_v1",
        ),
        strategy_key="total_goals_hgb_confirmed_under_mid_275_v1",
        strategy_display_name="大小球小球方向 · HGB模型共识 v1",
        signal_version="v1",
    )

    record = create_paper_record_from_queue_row(session, row, recorded_at=_now())

    assert record.strategy_key == "total_goals_hgb_confirmed_under_mid_275_v1"
    assert record.market_type == "total_goals"
    assert record.side == "under"
    assert record.line_bucket == "mid_2.75"
    assert record.signal_version == "v1"
    assert "model_consensus:confirmed" in record.risk_tags


def test_create_paper_record_allows_parallel_strategy_records_for_same_match(session):
    match = _seed_match(session)
    v1_row = _queue_row(match, status="candidate", line=Decimal("-0.50"))
    create_paper_record_from_queue_row(session, v1_row, recorded_at=_now())
    v2_row = _queue_row(
        match,
        status="candidate",
        line=Decimal("-0.50"),
        strategy_key="asian_away_cover_hgb_bucket_v2",
        strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
        signal_version="v2",
    )

    record = create_paper_record_from_queue_row(session, v2_row, recorded_at=_now())

    assert record.strategy_key == "asian_away_cover_hgb_bucket_v2"


def test_create_paper_record_rejects_non_candidate_and_duplicate_active(session):
    match = _seed_match(session)
    row = _queue_row(match, status="below_threshold", line=Decimal("-0.50"))

    with pytest.raises(ValueError, match="candidate"):
        create_paper_record_from_queue_row(session, row, recorded_at=_now())

    candidate = _queue_row(match, status="candidate", line=Decimal("-0.50"))
    create_paper_record_from_queue_row(session, candidate, recorded_at=_now())
    with pytest.raises(ValueError, match="duplicate"):
        create_paper_record_from_queue_row(session, candidate, recorded_at=_now())


def test_backfill_paper_record_from_historical_candidate_marks_manual_backfill(session):
    match = _seed_match(session)

    record = backfill_paper_record_from_candidate(
        session,
        match_id=match.id,
        recorded_at=_now(),
        market_line=Decimal("-0.50"),
        odds=Decimal("1.930"),
        model_probability=Decimal("0.6044"),
        market_probability=Decimal("0.4880"),
        edge=Decimal("0.1164"),
        manual_note="从 20260530 paper queue 报告补录",
        league_display_name="爱超",
        home_team_display_name="德罗赫达联",
        away_team_display_name="沃特福德联",
    )

    assert record.match_id == match.id
    assert record.strategy_display_name == ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME
    assert record.league_display_name == "爱超"
    assert record.home_team_display_name == "德罗赫达联"
    assert record.away_team_display_name == "沃特福德联"
    assert record.recommended_handicap == "客队 +0.50"
    assert record.original_market_line == Decimal("-0.50")
    assert record.current_market_line == Decimal("-0.50")
    assert record.original_odds == Decimal("1.930")
    assert record.current_odds == Decimal("1.930")
    assert record.model_probability == Decimal("0.6044")
    assert record.market_probability == Decimal("0.4880")
    assert record.edge == Decimal("0.1164")
    assert record.line_bucket == "away_underdog"
    assert record.status == "pending"
    assert record.is_manually_adjusted is True
    assert record.manual_note == "从 20260530 paper queue 报告补录"
    assert "manual_backfill" in record.risk_tags

    with pytest.raises(ValueError, match="duplicate"):
        backfill_paper_record_from_candidate(
            session,
            match_id=match.id,
            recorded_at=_now(),
            market_line=Decimal("-0.50"),
            odds=Decimal("1.930"),
            model_probability=Decimal("0.6044"),
            market_probability=Decimal("0.4880"),
            edge=Decimal("0.1164"),
            manual_note="重复补录",
            league_display_name="爱超",
            home_team_display_name="德罗赫达联",
            away_team_display_name="沃特福德联",
        )


def test_edit_paper_record_marks_manual_adjustment_and_preserves_original(session):
    match = _seed_match(session)
    record = create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )

    edited = edit_paper_record(
        session,
        record.id,
        current_market_line=Decimal("-0.25"),
        current_odds=Decimal("1.880"),
        manual_note="临场退盘，按人工确认盘口观察",
    )

    assert edited.original_market_line == Decimal("-0.50")
    assert edited.original_odds == Decimal("1.930")
    assert edited.current_market_line == Decimal("-0.25")
    assert edited.current_odds == Decimal("1.880")
    assert edited.recommended_handicap == "客队 +0.25"
    assert edited.is_manually_adjusted is True
    assert edited.manual_note == "临场退盘，按人工确认盘口观察"


def test_void_paper_record_excludes_record_from_settlement_summary(session):
    match = _seed_match(session, home_score=2, away_score=0, status="finished")
    record = create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )

    voided = void_paper_record(session, record.id)
    settled = settle_paper_records(session, settled_at=_now())
    workspace = build_paper_tracking_workspace(session, candidates=[])

    assert voided.status == "void"
    assert settled.settled_count == 0
    assert workspace.summary.total_records == 1
    assert workspace.summary.settled_records == 0
    assert workspace.summary.roi == Decimal("0.0000")


def test_settle_paper_records_uses_current_line_and_odds(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    record = create_paper_record_from_queue_row(
        session,
        _queue_row(match, status="candidate", line=Decimal("-0.50")),
        recorded_at=_now(),
    )
    edit_paper_record(
        session,
        record.id,
        current_market_line=Decimal("-0.25"),
        current_odds=Decimal("1.800"),
        manual_note="按人工确认盘口结算",
    )

    result = settle_paper_records(session, settled_at=_now())
    workspace = build_paper_tracking_workspace(session, candidates=[])

    session.refresh(record)
    assert result.settled_count == 1
    assert record.status == "settled"
    assert record.settlement_result == "half_win"
    assert record.profit_units == Decimal("0.400")
    assert workspace.summary.settled_records == 1
    assert workspace.summary.hit_rate == Decimal("1.0000")
    assert workspace.summary.roi == Decimal("0.4000")
    assert workspace.by_strategy[0].group_name == ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME
    assert workspace.by_manual_adjustment[0].group_name == "人工调整"


def test_settle_paper_records_supports_total_goals_records(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    record = create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            line=Decimal("2.75"),
            market_type="total_goals",
            side="under",
            recommended_handicap="小 2.75",
            odds=Decimal("2.000"),
            line_bucket="mid_2.75",
            risk_tags=("line_bucket:mid_2.75", "strategy:total_goals_bucket_v2"),
            strategy_key="total_goals_hgb_bucket_v2",
            strategy_display_name="大小球方向 · HGB分盘口桶 v2",
            signal_version="v2",
        ),
        recorded_at=_now(),
    )

    result = settle_paper_records(session, settled_at=_now())

    session.refresh(record)
    assert result.settled_count == 1
    assert result.unsettleable_count == 0
    assert record.status == "settled"
    assert record.settlement_result == "win"
    assert record.profit_units == Decimal("1.000")


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
    line_bucket: str = "away_underdog",
    risk_tags: tuple[str, ...] = ("line_bucket:away_underdog",),
    strategy_key: str = ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY,
    strategy_display_name: str = ASIAN_AWAY_COVER_HGB_EDGE_V1_NAME,
    signal_version: str = "v1",
    edge: Decimal = Decimal("0.1164"),
) -> PaperQueueRow:
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
        model_probability=Decimal("0.6044"),
        market_probability=Decimal("0.4880"),
        edge=edge,
        line_bucket=line_bucket,
        risk_tags=risk_tags,
        strategy_key=strategy_key,
        strategy_display_name=strategy_display_name,
        signal_version=signal_version,
    )


def _now() -> datetime:
    return datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

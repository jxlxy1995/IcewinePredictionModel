from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.models import League, Match, PaperRecommendationRecord, Team
from icewine_prediction.paper_strategy_performance_service import (
    PaperStrategyPerformanceFilters,
    build_paper_strategy_performance_report,
)


def test_build_paper_strategy_performance_report_summarizes_records(session):
    match = _seed_match(session)
    _add_record(
        session,
        match,
        strategy_key="asian_away_cover_hgb_edge_v1",
        strategy_display_name="Asian away HGB edge v1",
        market_type="asian_handicap",
        side="away_cover",
        line_bucket="away_underdog",
        status="settled",
        settlement_result="win",
        profit_units=Decimal("0.930"),
        edge=Decimal("0.1200"),
        scoring_edge=Decimal("0.1000"),
        is_manually_adjusted=False,
    )
    _add_record(
        session,
        match,
        strategy_key="asian_away_cover_hgb_edge_v1",
        strategy_display_name="Asian away HGB edge v1",
        market_type="asian_handicap",
        side="away_cover",
        line_bucket="away_underdog",
        status="settled",
        settlement_result="loss",
        profit_units=Decimal("-1.000"),
        edge=Decimal("0.0600"),
        scoring_edge=None,
        is_manually_adjusted=True,
    )
    _add_record(
        session,
        match,
        strategy_key="total_goals_hgb_bucket_v2",
        strategy_display_name="Total goals HGB bucket v2",
        market_type="total_goals",
        side="under",
        line_bucket="mid_2.75",
        status="pending",
        settlement_result=None,
        profit_units=None,
        edge=Decimal("0.0900"),
        scoring_edge=Decimal("0.0900"),
        is_manually_adjusted=False,
    )
    _add_record(
        session,
        match,
        strategy_key="voided_strategy",
        strategy_display_name="Voided Strategy",
        market_type="asian_handicap",
        side="home_cover",
        line_bucket="home_favorite",
        status="void",
        settlement_result=None,
        profit_units=None,
        edge=Decimal("0.2000"),
        scoring_edge=Decimal("0.2000"),
        is_manually_adjusted=False,
    )
    session.commit()

    report = build_paper_strategy_performance_report(session)

    assert report.summary.total_records == 4
    assert report.summary.active_records == 3
    assert report.summary.settled_records == 2
    assert report.summary.pending_records == 1
    assert report.summary.void_records == 1
    assert report.summary.total_profit_units == Decimal("-0.070")
    assert report.summary.roi == Decimal("-0.0350")
    assert report.summary.hit_rate == Decimal("0.5000")
    assert report.summary.low_sample_group_count == 8

    strategy_group = report.by_strategy[0]
    assert strategy_group.group_key == "asian_away_cover_hgb_edge_v1"
    assert strategy_group.record_count == 2
    assert strategy_group.settled_records == 2
    assert strategy_group.total_profit_units == Decimal("-0.070")
    assert strategy_group.roi == Decimal("-0.0350")
    assert strategy_group.hit_rate == Decimal("0.5000")
    assert strategy_group.warning == "low_sample"

    assert report.by_market_side[0].group_key == "asian_handicap:away_cover"
    assert report.by_manual_adjustment[0].group_key == "manual_adjusted"
    assert report.by_manual_adjustment[1].group_key == "original"
    assert {group.group_key for group in report.by_edge_bucket} == {"0.06-0.10", "0.10+"}
    assert report.by_settlement_result[0].group_key == "loss"
    assert report.by_settlement_result[1].group_key == "win"


def test_build_paper_strategy_performance_report_filters_by_kickoff_time(session):
    match = _seed_match(session)
    early_match = _seed_match(
        session,
        kickoff_time=datetime(2026, 5, 29, 22, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    _add_record(
        session,
        match,
        strategy_key="asian_away_cover_hgb_edge_v1",
        status="settled",
        settlement_result="win",
        profit_units=Decimal("0.930"),
    )
    _add_record(
        session,
        early_match,
        strategy_key="asian_away_cover_hgb_edge_v1",
        status="settled",
        settlement_result="loss",
        profit_units=Decimal("-1.000"),
    )
    session.commit()

    report = build_paper_strategy_performance_report(
        session,
        PaperStrategyPerformanceFilters(
            start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            end_time=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        ),
    )

    assert report.summary.total_records == 1
    assert report.summary.total_profit_units == Decimal("0.930")


def _seed_match(
    session,
    *,
    kickoff_time: datetime = datetime(2026, 5, 30, 2, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
) -> Match:
    league = session.query(League).filter(League.name == "Premier Division").one_or_none()
    if league is None:
        league = League(name="Premier Division", country_or_region="Ireland", level=1)
        session.add(league)
    home = session.query(Team).filter(Team.canonical_name == "Drogheda United").one_or_none()
    if home is None:
        home = Team(canonical_name="Drogheda United")
        session.add(home)
    away = session.query(Team).filter(Team.canonical_name == "Waterford").one_or_none()
    if away is None:
        away = Team(canonical_name="Waterford")
        session.add(away)
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time,
        status="finished",
        home_score=1,
        away_score=1,
        source_name="api_football",
        source_match_id="17446",
    )
    session.add_all([league, home, away, match])
    session.flush()
    return match


def _add_record(
    session,
    match: Match,
    *,
    strategy_key: str,
    strategy_display_name: str = "Asian away HGB edge v1",
    market_type: str = "asian_handicap",
    side: str = "away_cover",
    line_bucket: str = "away_underdog",
    status: str,
    settlement_result: str | None,
    profit_units: Decimal | None,
    edge: Decimal = Decimal("0.1200"),
    scoring_edge: Decimal | None = Decimal("0.1000"),
    is_manually_adjusted: bool = False,
) -> PaperRecommendationRecord:
    record = PaperRecommendationRecord(
        match_id=match.id,
        source_match_id=match.source_match_id,
        created_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        updated_at=datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        league_name=match.league.name,
        league_display_name="爱超",
        home_team_name=match.home_team.canonical_name,
        home_team_display_name="德罗赫达联",
        away_team_name=match.away_team.canonical_name,
        away_team_display_name="沃特福德联",
        kickoff_time=match.kickoff_time,
        strategy_key=strategy_key,
        strategy_display_name=strategy_display_name,
        model_name="raw_hgb_team_form_plus_all_markets",
        signal_version="v1",
        market_type=market_type,
        side=side,
        recommended_handicap="客队 +0.50",
        original_recommended_handicap="客队 +0.50",
        line_bucket=line_bucket,
        risk_tags=f"line_bucket:{line_bucket}",
        original_market_line=Decimal("-0.50"),
        original_odds=Decimal("1.930"),
        current_market_line=Decimal("-0.50"),
        current_odds=Decimal("1.930"),
        model_probability=Decimal("0.6500"),
        market_probability=Decimal("0.5000"),
        edge=edge,
        scoring_edge=scoring_edge,
        stake_units=Decimal("1.00"),
        status=status,
        is_manually_adjusted=is_manually_adjusted,
        settlement_result=settlement_result,
        profit_units=profit_units,
        settled_at=(
            datetime(2026, 5, 30, 5, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
            if status == "settled"
            else None
        ),
    )
    session.add(record)
    return record

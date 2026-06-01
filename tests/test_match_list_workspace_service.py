from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import event

from icewine_prediction.match_list_workspace_service import (
    build_match_detail,
    build_match_list_workspace,
    record_sync_run,
    select_match_list_sync_targets,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, OddsSnapshot, Team

BEIJING = ZoneInfo("Asia/Shanghai")


def test_match_list_workspace_defaults_to_today_through_tomorrow_noon_and_freshness(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Sanfrecce Hiroshima", logo_url="home.png")
    away = Team(canonical_name="Kawasaki Frontale", logo_url="away.png")
    later_home = Team(canonical_name="Nagoya Grampus")
    later_away = Team(canonical_name="Machida Zelvia")
    noon_home = Team(canonical_name="Cerezo Osaka")
    noon_away = Team(canonical_name="Vissel Kobe")
    session.add_all([league, home, away, later_home, later_away, noon_home, noon_away])
    session.flush()
    included = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        status="scheduled",
        source_match_id="j1-1",
    )
    included_tomorrow_noon = Match(
        league=league,
        home_team=noon_home,
        away_team=noon_away,
        kickoff_time=datetime(2026, 5, 31, 12, 0, tzinfo=BEIJING),
        status="scheduled",
        source_match_id="j1-3",
    )
    excluded = Match(
        league=league,
        home_team=later_home,
        away_team=later_away,
        kickoff_time=datetime(2026, 5, 31, 12, 1, tzinfo=BEIJING),
        status="scheduled",
        source_match_id="j1-2",
    )
    session.add_all([included, included_tomorrow_noon, excluded])
    session.flush()
    _add_asian_handicap_snapshot(session, included, line=Decimal("-0.25"))
    record_sync_run(
        session,
        sync_type="fixtures_results",
        started_at=now,
        finished_at=now,
        status="success",
        days=3,
        created_count=1,
        updated_count=2,
        skipped_count=0,
        requests_used=4,
    )
    record_sync_run(
        session,
        sync_type="odds",
        started_at=now,
        finished_at=now,
        status="success",
        days=2,
        created_count=3,
        updated_count=0,
        skipped_count=1,
        requests_used=2,
    )

    workspace = build_match_list_workspace(session, now=now)

    assert workspace.filters.start_time == "2026-05-30T00:00:00+08:00"
    assert workspace.filters.end_time == "2026-05-31T12:00:00+08:00"
    assert workspace.freshness.latest_fixtures_results_sync == "2026-05-30T10:00:00+08:00"
    assert workspace.freshness.latest_odds_sync == "2026-05-30T10:00:00+08:00"
    assert workspace.leagues[0].name == "J1 League"
    assert workspace.leagues[0].display_name == "\u65e5\u804c\u8054"
    assert workspace.total_matches == 2
    assert workspace.matches[0].match_id == included.id
    assert workspace.matches[1].match_id == included_tomorrow_noon.id
    assert workspace.matches[0].league_display_name == "\u65e5\u804c\u8054"
    assert workspace.matches[0].home_team_logo_url == "home.png"
    assert workspace.matches[0].has_odds is True
    assert workspace.matches[0].odds_status_key == "pending_fill"
    assert workspace.matches[0].odds_status_label == "\u5f85\u56de\u586b"
    assert workspace.matches[0].odds_summary.asian_handicap == "\u5ba2\u961f +0.25 @ 1.950"


def test_match_list_workspace_marks_started_unscored_matches_as_pending_result(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Sanfrecce Hiroshima")
    away = Team(canonical_name="Kawasaki Frontale")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING),
        status="scheduled",
        home_score=None,
        away_score=None,
    )
    session.add(match)
    session.commit()

    workspace = build_match_list_workspace(session, now=now, status_filter="live")

    assert workspace.total_matches == 1
    assert workspace.matches[0].match_id == match.id
    assert workspace.matches[0].status == "pending_result"
    assert workspace.matches[0].status_group == "live"


def test_match_list_workspace_hides_period_status_for_unscored_matches(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Sanfrecce Hiroshima")
    away = Team(canonical_name="Kawasaki Frontale")
    session.add_all([league, home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING),
        status="1h",
        status_short="1H",
        home_score=None,
        away_score=None,
    )
    session.add(match)
    session.commit()

    workspace = build_match_list_workspace(session, now=now, status_filter="live")

    assert workspace.total_matches == 1
    assert workspace.matches[0].match_id == match.id
    assert workspace.matches[0].status == "pending_result"
    assert workspace.matches[0].status_group == "live"


def test_match_list_workspace_live_filter_applies_before_result_limit(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    session.add(league)
    session.flush()
    for index in range(3):
        home = Team(canonical_name=f"Finished Home {index}")
        away = Team(canonical_name=f"Finished Away {index}")
        session.add_all([home, away])
        session.flush()
        session.add(
            Match(
                league=league,
                home_team=home,
                away_team=away,
                kickoff_time=datetime(2026, 5, 30, 8, index, tzinfo=BEIJING),
                status="finished",
                home_score=1,
                away_score=0,
            )
        )
    live_home = Team(canonical_name="Live Home")
    live_away = Team(canonical_name="Live Away")
    session.add_all([live_home, live_away])
    session.flush()
    live_match = Match(
        league=league,
        home_team=live_home,
        away_team=live_away,
        kickoff_time=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING),
        status="scheduled",
        home_score=None,
        away_score=None,
    )
    session.add(live_match)
    session.commit()

    workspace = build_match_list_workspace(session, now=now, status_filter="live", limit=2)

    assert workspace.total_matches == 1
    assert workspace.matches[0].match_id == live_match.id


def test_match_list_workspace_filters_by_status_odds_league_and_search(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    j1 = League(name="J1 League", country_or_region="Japan", level=1)
    k1 = League(name="K League 1", country_or_region="Korea", level=1)
    hiroshima = Team(canonical_name="Sanfrecce Hiroshima")
    kawasaki = Team(canonical_name="Kawasaki Frontale")
    ulsan = Team(canonical_name="Ulsan HD FC")
    daegu = Team(canonical_name="Daegu FC")
    session.add_all([j1, k1, hiroshima, kawasaki, ulsan, daegu])
    session.flush()
    j1_match = Match(
        league=j1,
        home_team=hiroshima,
        away_team=kawasaki,
        kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING),
        status="scheduled",
    )
    k1_match = Match(
        league=k1,
        home_team=ulsan,
        away_team=daegu,
        kickoff_time=datetime(2026, 5, 30, 15, 30, tzinfo=BEIJING),
        status="finished",
        home_score=2,
        away_score=1,
    )
    session.add_all([j1_match, k1_match])
    session.flush()
    _add_asian_handicap_snapshot(session, j1_match, line=Decimal("0.50"))

    workspace = build_match_list_workspace(
        session,
        now=now,
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        league_name="J1 League",
        status_filter="not_started",
        odds_filter="with_odds",
        search="hiro",
    )

    assert workspace.total_matches == 1
    assert workspace.matches[0].match_id == j1_match.id
    assert workspace.matches[0].status_group == "not_started"


def test_match_list_workspace_classifies_and_filters_odds_statuses(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    session.add(league)
    session.flush()
    no_odds = _add_match(session, league, "No Odds", datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING))
    early = _add_match(session, league, "Early", datetime(2026, 5, 30, 15, 0, tzinfo=BEIJING))
    near = _add_match(session, league, "Near", datetime(2026, 5, 30, 12, 0, tzinfo=BEIJING))
    close = _add_match(session, league, "Close", datetime(2026, 5, 30, 10, 20, tzinfo=BEIJING))
    pending = _add_match(
        session,
        league,
        "Pending",
        datetime(2026, 5, 30, 8, 0, tzinfo=BEIJING),
        status="finished",
        home_score=1,
        away_score=0,
    )
    filled = _add_match(
        session,
        league,
        "Filled",
        datetime(2026, 5, 30, 7, 0, tzinfo=BEIJING),
        status="finished",
        home_score=1,
        away_score=0,
    )
    _add_live_odds_snapshot(session, early, captured_at=datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING))
    _add_live_odds_snapshot(session, near, captured_at=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING))
    _add_live_odds_snapshot(session, close, captured_at=datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING))
    _add_live_odds_snapshot(session, pending, captured_at=datetime(2026, 5, 30, 7, 30, tzinfo=BEIJING))
    _add_complete_historical_odds(session, filled)
    session.commit()

    workspace = build_match_list_workspace(
        session,
        now=now,
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        odds_filter="none,near,pending_fill",
    )

    assert [match.match_id for match in workspace.matches] == [pending.id, near.id, no_odds.id]
    assert [match.odds_status_label for match in workspace.matches] == [
        "\u5f85\u56de\u586b",
        "\u8fd1\u76d8",
        "\u65e0\u8d54\u7387",
    ]
    assert workspace.filters.odds_filter == "none,near,pending_fill"


def test_match_list_workspace_limits_odds_status_work_to_filtered_matches(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    session.add(league)
    session.flush()
    inside = _add_match(session, league, "Inside", datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING))
    for index in range(80):
        _add_match(
            session,
            league,
            f"Outside {index}",
            datetime(2026, 6, 30, 13, 0, tzinfo=BEIJING) + timedelta(days=index),
        )
    session.commit()

    statement_count = 0

    def count_statement(*_args):
        nonlocal statement_count
        statement_count += 1

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        workspace = build_match_list_workspace(
            session,
            now=now,
            start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
            end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    assert [match.match_id for match in workspace.matches] == [inside.id]
    assert statement_count < 35


def test_match_list_workspace_batches_odds_status_for_many_visible_matches(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    session.add(league)
    session.flush()
    for index in range(80):
        _add_match(
            session,
            league,
            f"Inside {index}",
            datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING) + timedelta(minutes=index),
        )
    session.commit()

    statement_count = 0

    def count_statement(*_args):
        nonlocal statement_count
        statement_count += 1

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        workspace = build_match_list_workspace(
            session,
            now=now,
            start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
            end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    assert workspace.total_matches == 80
    assert statement_count < 35


def test_select_match_list_sync_targets_uses_full_filters_without_visible_limit(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    j1 = League(name="J1 League", country_or_region="Japan", level=1)
    k1 = League(name="K League 1", country_or_region="Korea", level=1)
    session.add_all([j1, k1])
    session.flush()
    selected_matches = []
    for index in range(3):
        home = Team(canonical_name=f"Sanfrecce Sync {index}")
        away = Team(canonical_name=f"Kawasaki Sync {index}")
        session.add_all([home, away])
        session.flush()
        match = Match(
            league=j1,
            home_team=home,
            away_team=away,
            kickoff_time=datetime(2026, 5, 30, 13, index, tzinfo=BEIJING),
            status="scheduled",
        )
        session.add(match)
        session.flush()
        _add_asian_handicap_snapshot(session, match, line=Decimal("-0.50"))
        selected_matches.append(match)
    other_home = Team(canonical_name="Ulsan Sync")
    other_away = Team(canonical_name="Daegu Sync")
    session.add_all([other_home, other_away])
    session.flush()
    session.add(
        Match(
            league=k1,
            home_team=other_home,
            away_team=other_away,
            kickoff_time=datetime(2026, 5, 30, 13, 30, tzinfo=BEIJING),
            status="scheduled",
        )
    )
    session.commit()

    targets = select_match_list_sync_targets(
        session,
        now=now,
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        league_name="J1 League",
        status_filter="not_started",
        odds_filter="with_odds",
        search="sync",
    )

    assert [match.id for match in targets] == [match.id for match in selected_matches]


def test_select_match_list_sync_targets_filters_by_multiple_odds_statuses(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    league = League(name="J1 League", country_or_region="Japan", level=1)
    session.add(league)
    session.flush()
    no_odds = _add_match(session, league, "No Sync Odds", datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING))
    close = _add_match(session, league, "Close Sync Odds", datetime(2026, 5, 30, 10, 20, tzinfo=BEIJING))
    filled = _add_match(
        session,
        league,
        "Filled Sync Odds",
        datetime(2026, 5, 30, 7, 0, tzinfo=BEIJING),
        status="finished",
        home_score=2,
        away_score=1,
    )
    _add_live_odds_snapshot(session, close, captured_at=datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING))
    _add_complete_historical_odds(session, filled)
    session.commit()

    targets = select_match_list_sync_targets(
        session,
        now=now,
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
        odds_filter="none,close",
    )

    assert [match.id for match in targets] == [close.id, no_odds.id]


def test_match_detail_includes_odds_and_recommendation_placeholders(session):
    league = League(name="J1 League", country_or_region="Japan", level=1)
    home = Team(canonical_name="Sanfrecce Hiroshima", logo_url="home.png")
    away = Team(canonical_name="Kawasaki Frontale", logo_url="away.png")
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING),
        status="scheduled",
    )
    session.add_all([league, home, away, match])
    session.flush()
    _add_asian_handicap_snapshot(session, match, line=Decimal("-0.50"))

    detail = build_match_detail(session, match_id=match.id)

    assert detail is not None
    assert detail.match_id == match.id
    assert detail.home_team_logo_url == "home.png"
    assert detail.has_odds is True
    assert detail.odds_status_key == "early"
    assert detail.odds_status_label == "\u65e9\u76d8"
    assert detail.team_data_note == "\u5f85\u63a5\u5165"
    assert detail.odds_summary.asian_handicap == "\u5ba2\u961f +0.50 @ 1.950"
    assert detail.paper_recommendation_summary.label == "\u6682\u65e0\u7eb8\u9762\u63a8\u8350\u8bb0\u5f55"
    assert detail.formal_recommendation_summary.label == "\u6682\u65e0\u6b63\u5f0f\u63a8\u8350\u8bb0\u5f55"


def _add_asian_handicap_snapshot(session, match: Match, *, line: Decimal):
    session.add_all(
        [
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="ah",
                market_name="Asian Handicap",
                market_line=line,
                outcome_side="home",
                odds=Decimal("1.900"),
                snapshot_time=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING),
                period="pre_match",
            ),
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker="pinnacle",
                market_type="asian_handicap",
                market_id="ah",
                market_name="Asian Handicap",
                market_line=line,
                outcome_side="away",
                odds=Decimal("1.950"),
                snapshot_time=datetime(2026, 5, 30, 9, 30, tzinfo=BEIJING),
                period="pre_match",
            ),
        ]
    )
    session.commit()


def _add_match(
    session,
    league: League,
    prefix: str,
    kickoff_time: datetime,
    *,
    status: str = "scheduled",
    home_score: int | None = None,
    away_score: int | None = None,
) -> Match:
    home = Team(canonical_name=f"{prefix} Home")
    away = Team(canonical_name=f"{prefix} Away")
    session.add_all([home, away])
    session.flush()
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff_time,
        status=status,
        home_score=home_score,
        away_score=away_score,
        source_match_id=prefix.lower().replace(" ", "-"),
    )
    session.add(match)
    session.flush()
    return match


def _add_live_odds_snapshot(session, match: Match, *, captured_at: datetime) -> None:
    session.add(
        OddsSnapshot(
            match_id=match.id,
            captured_at=captured_at,
            data_source="api_football",
            bookmaker="Pinnacle",
            asian_handicap=Decimal("-0.25"),
            home_odds=Decimal("1.900"),
            away_odds=Decimal("1.950"),
        )
    )


def _add_complete_historical_odds(session, match: Match) -> None:
    snapshot_time = match.kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=6)
    markets = [
        ("asian_handicap", Decimal("-0.25"), ("home", "away")),
        ("total_goals", Decimal("2.50"), ("over", "under")),
        ("match_winner", Decimal("0.00"), ("home", "draw", "away")),
    ]
    counts = {market_type: 0 for market_type, _, _ in markets}
    for index in range(120):
        market_type, line, sides = markets[index % len(markets)]
        side = sides[counts[market_type] % len(sides)]
        counts[market_type] += 1
        session.add(
            HistoricalOddsSnapshot(
                match_id=match.id,
                source_name="oddspapi",
                source_fixture_id=match.source_match_id or str(match.id),
                bookmaker="pinnacle",
                market_type=market_type,
                market_id=f"{market_type}-{index}",
                market_name=market_type,
                market_line=line,
                outcome_side=side,
                odds=Decimal("1.900"),
                snapshot_time=snapshot_time,
                period="fulltime",
            )
        )

from datetime import datetime, timedelta
from dataclasses import replace
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import (
    HistoricalOddsSnapshotInput,
    build_historical_odds_coverage_report,
    sample_historical_odds_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import HistoricalOddsSnapshot, League, Match, Team


def _match(session):
    league = League(
        name="La Liga",
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
    )
    home_team = Team(canonical_name="Mallorca")
    away_team = Team(canonical_name="Oviedo")
    session.add_all([league, home_team, away_team])
    session.flush()
    match = Match(
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_time=datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        season=2025,
        status="finished",
        source_name="api_football",
        source_match_id="1391195",
    )
    session.add(match)
    session.commit()
    return match


def _snapshot(match_id: int, odds: Decimal = Decimal("1.91")):
    return HistoricalOddsSnapshotInput(
        match_id=match_id,
        source_name="oddspapi",
        source_fixture_id="fixture-1",
        bookmaker="pinnacle",
        market_type="asian_handicap",
        market_id="1070",
        market_name="Asian Handicap",
        market_line=Decimal("-0.25"),
        outcome_side="home",
        odds=odds,
        snapshot_time=datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC")),
        period="fulltime",
        raw_payload='{"sample": true}',
    )


def test_store_historical_odds_snapshots_inserts_once_for_same_unique_key(session):
    match = _match(session)
    first = _snapshot(match.id, odds=Decimal("1.91"))
    duplicate = _snapshot(match.id, odds=Decimal("1.95"))

    result = store_historical_odds_snapshots(session, [first, duplicate])

    saved = session.query(HistoricalOddsSnapshot).one()
    assert result.inserted_count == 1
    assert result.skipped_duplicate_count == 1
    assert saved.odds == Decimal("1.910")


def test_build_historical_odds_coverage_report_counts_matches_and_market_rows(session):
    match = _match(session)
    store_historical_odds_snapshots(
        session,
        [
            _snapshot(match.id),
            replace(
                _snapshot(match.id),
                market_type="total_goals",
                market_id="10170",
                market_name="Over Under Full Time",
                market_line=Decimal("2.25"),
                outcome_side="over",
                odds=Decimal("1.88"),
            ),
        ],
    )

    report = build_historical_odds_coverage_report(session, season=2025)

    assert report.match_count == 1
    assert report.snapshot_count == 2
    assert report.asian_handicap_count == 1
    assert report.total_goals_count == 1


def test_sample_historical_odds_snapshots_keeps_first_last_and_even_time_shape():
    match_id = 1
    snapshots = [
        replace(
            _snapshot(match_id),
            odds=Decimal("1.50") + Decimal(index) / Decimal("100"),
            snapshot_time=datetime(2026, 5, 23, index, 0, tzinfo=ZoneInfo("UTC")),
        )
        for index in range(24)
    ]

    sampled = sample_historical_odds_snapshots(
        snapshots,
        max_snapshots_per_match=6,
    )

    assert len(sampled) == 6
    assert sampled[0].snapshot_time == datetime(2026, 5, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert sampled[-1].snapshot_time == datetime(2026, 5, 23, 23, 0, tzinfo=ZoneInfo("UTC"))
    assert sampled == sorted(sampled, key=lambda snapshot: snapshot.snapshot_time)


def test_sample_historical_odds_snapshots_allocates_limit_across_groups():
    match_id = 1
    snapshots = []
    for market_type, outcome_side in [
        ("asian_handicap", "home"),
        ("asian_handicap", "away"),
        ("total_goals", "over"),
        ("total_goals", "under"),
    ]:
        for index in range(10):
            snapshots.append(
                replace(
                    _snapshot(match_id),
                    market_type=market_type,
                    outcome_side=outcome_side,
                    snapshot_time=datetime(
                        2026,
                        5,
                        23,
                        index,
                        0,
                        tzinfo=ZoneInfo("UTC"),
                    ),
                )
            )

    sampled = sample_historical_odds_snapshots(
        snapshots,
        max_snapshots_per_match=8,
    )

    counts_by_group = {}
    for snapshot in sampled:
        key = (snapshot.market_type, snapshot.outcome_side)
        counts_by_group[key] = counts_by_group.get(key, 0) + 1

    assert len(sampled) == 8
    assert set(counts_by_group.values()) == {2}


def test_sample_historical_odds_snapshots_limits_each_market_type_before_kickoff():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for bookmaker in ["pinnacle", "sbobet"]:
        for market_type, outcome_side in [
            ("asian_handicap", "home"),
            ("asian_handicap", "away"),
            ("total_goals", "over"),
            ("total_goals", "under"),
        ]:
            for index in range(80):
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        bookmaker=bookmaker,
                        market_type=market_type,
                        outcome_side=outcome_side,
                        snapshot_time=kickoff_time.astimezone(ZoneInfo("UTC"))
                        - timedelta(minutes=index * 12),
                    )
                )
        snapshots.append(
            replace(
                _snapshot(match_id),
                bookmaker=bookmaker,
                market_type="asian_handicap",
                outcome_side="home",
                snapshot_time=kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=25),
            )
        )

    sampled = sample_historical_odds_snapshots(
        snapshots,
        kickoff_time=kickoff_time,
        max_snapshots_per_market_type=50,
    )

    counts_by_market_type = {}
    bookmakers = set()
    for snapshot in sampled:
        counts_by_market_type[snapshot.market_type] = (
            counts_by_market_type.get(snapshot.market_type, 0) + 1
        )
        bookmakers.add(snapshot.bookmaker)
        assert kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=24) <= snapshot.snapshot_time
        assert snapshot.snapshot_time <= kickoff_time.astimezone(ZoneInfo("UTC"))

    assert counts_by_market_type == {
        "asian_handicap": 50,
        "total_goals": 50,
    }
    assert bookmakers == {"pinnacle", "sbobet"}


def test_sample_historical_odds_snapshots_preserves_main_market_pairs():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for index in range(80):
        snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
        for outcome_side in ["over", "under"]:
            snapshots.append(
                replace(
                    _snapshot(match_id),
                    market_type="total_goals",
                    market_id="total-25",
                    market_name="Over Under Full Time",
                    market_line=Decimal("2.50"),
                    outcome_side=outcome_side,
                    snapshot_time=snapshot_time,
                )
            )

    sampled = sample_historical_odds_snapshots(
        snapshots,
        kickoff_time=kickoff_time,
        max_snapshots_per_market_type=50,
    )

    counts_by_time = {}
    for snapshot in sampled:
        key = (snapshot.bookmaker, snapshot.market_type, snapshot.market_line, snapshot.snapshot_time)
        counts_by_time[key] = counts_by_time.get(key, 0) + 1

    assert len(sampled) == 50
    assert set(counts_by_time.values()) == {2}

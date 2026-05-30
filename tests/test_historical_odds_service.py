from datetime import datetime, timedelta
from dataclasses import replace
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.historical_odds_service import (
    HistoricalOddsSnapshotInput,
    build_historical_odds_market_coverage,
    build_historical_odds_coverage_report,
    sample_oddspapi_training_snapshots,
    sample_historical_odds_snapshots,
    store_historical_odds_raw_snapshots,
    store_historical_odds_snapshots,
)
from icewine_prediction.models import HistoricalOddsRawSnapshot, HistoricalOddsSnapshot, League, Match, Team


def _match(
    session,
    *,
    source_match_id: str = "1391195",
    league_name: str = "La Liga",
    home_team_name: str = "Mallorca",
    away_team_name: str = "Oviedo",
):
    league = League(
        name=league_name,
        country_or_region="Spain",
        level=1,
        source_name="api_football",
        source_league_id="140",
    )
    home_team = Team(canonical_name=home_team_name)
    away_team = Team(canonical_name=away_team_name)
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
        source_match_id=source_match_id,
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


def test_store_historical_odds_raw_snapshots_skips_existing_unique_key(session):
    match = _match(session)
    first = _snapshot(match.id, odds=Decimal("1.91"))
    duplicate = _snapshot(match.id, odds=Decimal("1.95"))
    away = replace(first, outcome_side="away", odds=Decimal("1.99"))

    first_result = store_historical_odds_raw_snapshots(session, [first, away])
    second_result = store_historical_odds_raw_snapshots(session, [duplicate, away])

    saved = (
        session.query(HistoricalOddsRawSnapshot)
        .filter(HistoricalOddsRawSnapshot.outcome_side == "home")
        .one()
    )
    assert first_result.inserted_count == 2
    assert first_result.skipped_duplicate_count == 0
    assert second_result.inserted_count == 0
    assert second_result.skipped_duplicate_count == 2
    assert saved.odds == Decimal("1.910")


def test_store_historical_odds_snapshots_treats_market_line_as_unique_key(session):
    match = _match(session)
    snapshot_time = datetime(2026, 5, 23, 18, 0, tzinfo=ZoneInfo("UTC"))
    snapshots = [
        replace(
            _snapshot(match.id),
            market_id="total-goals",
            market_type="total_goals",
            market_name="Over Under Full Time",
            market_line=Decimal("2.50"),
            outcome_side="over",
            snapshot_time=snapshot_time,
        ),
        replace(
            _snapshot(match.id),
            market_id="total-goals",
            market_type="total_goals",
            market_name="Over Under Full Time",
            market_line=Decimal("2.50"),
            outcome_side="under",
            snapshot_time=snapshot_time,
        ),
        replace(
            _snapshot(match.id),
            market_id="total-goals",
            market_type="total_goals",
            market_name="Over Under Full Time",
            market_line=Decimal("2.75"),
            outcome_side="over",
            snapshot_time=snapshot_time,
        ),
        replace(
            _snapshot(match.id),
            market_id="total-goals",
            market_type="total_goals",
            market_name="Over Under Full Time",
            market_line=Decimal("2.75"),
            outcome_side="under",
            snapshot_time=snapshot_time,
        ),
    ]

    result = store_historical_odds_snapshots(session, snapshots)

    saved_lines = {
        row.market_line
        for row in session.query(HistoricalOddsSnapshot).order_by(HistoricalOddsSnapshot.market_line)
    }
    assert result.inserted_count == 4
    assert result.skipped_duplicate_count == 0
    assert saved_lines == {Decimal("2.500"), Decimal("2.750")}


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


def test_build_historical_odds_coverage_report_counts_match_winner_rows(session):
    match = _match(session)
    store_historical_odds_snapshots(
        session,
        [
            replace(
                _snapshot(match.id),
                market_type="match_winner",
                market_id="9001",
                market_name="1X2 Full Time",
                market_line=Decimal("0"),
                outcome_side="home",
                odds=Decimal("2.10"),
            ),
        ],
    )

    report = build_historical_odds_coverage_report(session, season=2025)

    assert report.match_winner_count == 1


def test_build_historical_odds_market_coverage_classifies_missing_markets(session):
    full_match = _match(session)
    only_two_markets = _match(
        session,
        source_match_id="1391196",
        league_name="Championship",
        home_team_name="Cardiff",
        away_team_name="Swansea",
    )
    blank_match = _match(
        session,
        source_match_id="1391197",
        league_name="Premier League",
        home_team_name="Wolves",
        away_team_name="Leeds",
    )
    store_historical_odds_snapshots(
        session,
        [
            _snapshot(full_match.id),
            replace(
                _snapshot(full_match.id),
                market_type="total_goals",
                market_id="10170",
                market_name="Over Under Full Time",
                market_line=Decimal("2.25"),
                outcome_side="over",
            ),
            replace(
                _snapshot(full_match.id),
                market_type="match_winner",
                market_id="9001",
                market_name="1X2 Full Time",
                market_line=Decimal("0"),
                outcome_side="home",
            ),
            _snapshot(only_two_markets.id),
            replace(
                _snapshot(only_two_markets.id),
                market_type="total_goals",
                market_id="10170",
                market_name="Over Under Full Time",
                market_line=Decimal("2.25"),
                outcome_side="over",
            ),
        ],
    )

    coverage = build_historical_odds_market_coverage(session, season=2025)

    assert coverage.total_finished_matches == 3
    assert coverage.blank_count == 1
    assert coverage.complete_count == 1
    assert coverage.missing_match_winner_count == 2
    assert coverage.missing_asian_handicap_count == 1
    assert coverage.missing_total_goals_count == 1
    assert coverage.status_by_match_id == {
        full_match.id: "complete",
        only_two_markets.id: "missing_match_winner",
        blank_match.id: "blank",
    }


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


def test_sample_oddspapi_training_snapshots_prefers_24_hour_100_snapshot_target():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for market_type, outcome_sides in [
        ("asian_handicap", ["home", "away"]),
        ("total_goals", ["over", "under"]),
    ]:
        for index in range(80):
            snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
            for outcome_side in outcome_sides:
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        market_type=market_type,
                        outcome_side=outcome_side,
                        snapshot_time=snapshot_time,
                    )
                )

    sampled = sample_oddspapi_training_snapshots(snapshots, kickoff_time=kickoff_time)

    counts_by_market_type = {}
    for snapshot in sampled:
        counts_by_market_type[snapshot.market_type] = (
            counts_by_market_type.get(snapshot.market_type, 0) + 1
        )
        assert kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=24) <= snapshot.snapshot_time
        assert snapshot.snapshot_time <= kickoff_time.astimezone(ZoneInfo("UTC"))

    assert len(sampled) == 100
    assert counts_by_market_type == {
        "asian_handicap": 50,
        "total_goals": 50,
    }


def test_sample_oddspapi_training_snapshots_keeps_match_winner_triplets():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for market_type, outcome_sides in [
        ("asian_handicap", ["home", "away"]),
        ("total_goals", ["over", "under"]),
        ("match_winner", ["home", "draw", "away"]),
    ]:
        for index in range(80):
            snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
            for outcome_side in outcome_sides:
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        market_type=market_type,
                        market_line=Decimal("0") if market_type == "match_winner" else Decimal("2.50"),
                        outcome_side=outcome_side,
                        snapshot_time=snapshot_time,
                    )
                )

    sampled = sample_oddspapi_training_snapshots(snapshots, kickoff_time=kickoff_time)

    counts_by_market_type = {}
    sides_by_match_winner_time = {}
    for snapshot in sampled:
        counts_by_market_type[snapshot.market_type] = (
            counts_by_market_type.get(snapshot.market_type, 0) + 1
        )
        if snapshot.market_type == "match_winner":
            sides_by_match_winner_time.setdefault(snapshot.snapshot_time, set()).add(
                snapshot.outcome_side
            )

    assert len(sampled) == 151
    assert counts_by_market_type == {
        "asian_handicap": 50,
        "total_goals": 50,
        "match_winner": 51,
    }
    assert {"home", "draw", "away"} in sides_by_match_winner_time.values()


def test_sample_oddspapi_training_snapshots_accepts_4_hour_30_snapshot_floor():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for market_type, outcome_sides in [
        ("asian_handicap", ["home", "away"]),
        ("total_goals", ["over", "under"]),
    ]:
        for index in range(20):
            snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
            for outcome_side in outcome_sides:
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        market_type=market_type,
                        outcome_side=outcome_side,
                        snapshot_time=snapshot_time,
                    )
                )

    sampled = sample_oddspapi_training_snapshots(snapshots, kickoff_time=kickoff_time)

    assert len(sampled) == 30
    assert all(
        kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=4)
        <= snapshot.snapshot_time
        <= kickoff_time.astimezone(ZoneInfo("UTC"))
        for snapshot in sampled
    )


def test_sample_oddspapi_training_snapshots_keeps_sparse_complete_24_hour_markets():
    match_id = 1
    kickoff_time = datetime(2026, 5, 30, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshot_times = [
        kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=23, minutes=58),
        kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=23, minutes=57),
        kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=23, minutes=56),
    ]
    snapshots = []
    for snapshot_time in snapshot_times:
        for market_type, market_line, outcome_sides in [
            ("asian_handicap", Decimal("-0.75"), ["home", "away"]),
            ("total_goals", Decimal("3.25"), ["over", "under"]),
            ("match_winner", Decimal("0"), ["home", "draw", "away"]),
        ]:
            for outcome_side in outcome_sides:
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        market_type=market_type,
                        market_id=f"{market_type}-{market_line}",
                        market_line=market_line,
                        outcome_side=outcome_side,
                        snapshot_time=snapshot_time,
                    )
                )

    sampled = sample_oddspapi_training_snapshots(snapshots, kickoff_time=kickoff_time)

    counts_by_market_type = {}
    for snapshot in sampled:
        counts_by_market_type[snapshot.market_type] = (
            counts_by_market_type.get(snapshot.market_type, 0) + 1
        )
    assert len(sampled) == 21
    assert counts_by_market_type == {
        "asian_handicap": 6,
        "total_goals": 6,
        "match_winner": 9,
    }


def test_sample_oddspapi_training_snapshots_keeps_compact_neighbor_groups_together():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for index in range(20):
        snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
        for line in [Decimal("3.25"), Decimal("3.50"), Decimal("3.75")]:
            for outcome_side in ["over", "under"]:
                snapshots.append(
                    replace(
                        _snapshot(match_id),
                        market_type="total_goals",
                        market_id=f"total-{line}",
                        market_line=line,
                        outcome_side=outcome_side,
                        snapshot_time=snapshot_time,
                    )
                )

    sampled = sample_oddspapi_training_snapshots(
        snapshots,
        kickoff_time=kickoff_time,
        target_snapshots_per_market_type=24,
    )

    lines_by_time = {}
    for snapshot in sampled:
        lines_by_time.setdefault(snapshot.snapshot_time, set()).add(snapshot.market_line)

    assert len(sampled) == 24
    assert {frozenset(lines) for lines in lines_by_time.values()} == {
        frozenset({Decimal("3.25"), Decimal("3.50"), Decimal("3.75")})
    }


def test_sample_oddspapi_training_snapshots_drops_incomplete_lines_inside_time_group():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=1)
    snapshots = [
        replace(
            _snapshot(match_id),
            market_type="total_goals",
            market_id="total-35",
            market_name="Over Under Full Time",
            market_line=Decimal("3.50"),
            outcome_side="over",
            snapshot_time=snapshot_time,
        ),
        replace(
            _snapshot(match_id),
            market_type="total_goals",
            market_id="total-35",
            market_name="Over Under Full Time",
            market_line=Decimal("3.50"),
            outcome_side="under",
            snapshot_time=snapshot_time,
        ),
        replace(
            _snapshot(match_id),
            market_type="total_goals",
            market_id="total-375",
            market_name="Over Under Full Time",
            market_line=Decimal("3.75"),
            outcome_side="under",
            snapshot_time=snapshot_time,
        ),
    ]

    sampled = sample_oddspapi_training_snapshots(
        snapshots,
        kickoff_time=kickoff_time,
        target_snapshots_per_market_type=10,
    )

    assert {(snapshot.market_line, snapshot.outcome_side) for snapshot in sampled} == {
        (Decimal("3.50"), "over"),
        (Decimal("3.50"), "under"),
    }


def test_sample_oddspapi_training_snapshots_drops_incomplete_match_winner_triplet():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    complete_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=1)
    incomplete_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(hours=2)
    snapshots = []
    for outcome_side in ["home", "draw", "away"]:
        snapshots.append(
            replace(
                _snapshot(match_id),
                market_type="match_winner",
                market_id="1x2",
                market_name="1X2 Full Time",
                market_line=Decimal("0"),
                outcome_side=outcome_side,
                snapshot_time=complete_time,
            )
        )
    for outcome_side in ["draw", "away"]:
        snapshots.append(
            replace(
                _snapshot(match_id),
                market_type="match_winner",
                market_id="1x2",
                market_name="1X2 Full Time",
                market_line=Decimal("0"),
                outcome_side=outcome_side,
                snapshot_time=incomplete_time,
            )
        )

    sampled = sample_oddspapi_training_snapshots(
        snapshots,
        kickoff_time=kickoff_time,
        target_snapshots_per_market_type=10,
    )

    assert {snapshot.snapshot_time for snapshot in sampled} == {complete_time}
    assert {snapshot.outcome_side for snapshot in sampled} == {"home", "draw", "away"}


def test_sample_oddspapi_training_snapshots_final_limit_does_not_split_complete_groups():
    match_id = 1
    kickoff_time = datetime(2026, 5, 24, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    snapshots = []
    for market_type, outcome_sides, market_lines in [
        (
            "asian_handicap",
            ["home", "away"],
            [Decimal("-1.00"), Decimal("-0.75"), Decimal("-0.50")],
        ),
        (
            "total_goals",
            ["over", "under"],
            [Decimal("3.00"), Decimal("3.25"), Decimal("3.50")],
        ),
        ("match_winner", ["home", "draw", "away"], [Decimal("0")]),
    ]:
        for index in range(80):
            snapshot_time = kickoff_time.astimezone(ZoneInfo("UTC")) - timedelta(minutes=index * 10)
            for market_line in market_lines:
                for outcome_side in outcome_sides:
                    snapshots.append(
                        replace(
                            _snapshot(match_id),
                            market_type=market_type,
                            market_id=f"{market_type}-{market_line}",
                            market_line=market_line,
                            outcome_side=outcome_side,
                            snapshot_time=snapshot_time,
                        )
                    )

    sampled = sample_oddspapi_training_snapshots(snapshots, kickoff_time=kickoff_time)

    required_sides = {
        "asian_handicap": {"home", "away"},
        "total_goals": {"over", "under"},
        "match_winner": {"home", "draw", "away"},
    }
    sides_by_group = {}
    for snapshot in sampled:
        key = (
            snapshot.bookmaker,
            snapshot.market_type,
            snapshot.snapshot_time,
            snapshot.market_line,
        )
        sides_by_group.setdefault(key, set()).add(snapshot.outcome_side)

    assert len(sampled) <= 151
    assert all(
        required_sides[market_type].issubset(sides)
        for (_, market_type, _, _), sides in sides_by_group.items()
    )

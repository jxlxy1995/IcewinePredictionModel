from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.odds_provider_selection_service import THE_ODDS_API_SOURCE_NAME
from icewine_prediction.sources.the_odds_api_odds_mapper import map_the_odds_api_event_odds


def test_map_the_odds_api_event_odds_maps_three_pinnacle_markets():
    event = {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "commence_time": "2026-06-26T19:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": "2026-06-26T18:45:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": "2026-06-26T18:45:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": "Chelsea", "price": 3.40},
                        ],
                    },
                    {
                        "key": "spreads",
                        "last_update": "2026-06-26T18:46:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.91, "point": -0.25},
                            {"name": "Chelsea", "price": 1.99, "point": 0.25},
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": "2026-06-26T18:47:00Z",
                        "outcomes": [
                            {"name": "Over", "price": 1.88, "point": 2.5},
                            {"name": "Under", "price": 2.02, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }

    snapshots = map_the_odds_api_event_odds(match_id=42, event=event)

    assert len(snapshots) == 7
    assert {snapshot.source_name for snapshot in snapshots} == {THE_ODDS_API_SOURCE_NAME}
    assert {snapshot.bookmaker for snapshot in snapshots} == {"pinnacle"}
    assert {snapshot.market_type for snapshot in snapshots} == {
        "match_winner",
        "asian_handicap",
        "total_goals",
    }
    assert [
        snapshot.outcome_side
        for snapshot in snapshots
        if snapshot.market_type == "match_winner"
    ] == [
        "home",
        "draw",
        "away",
    ]
    asian = [snapshot for snapshot in snapshots if snapshot.market_type == "asian_handicap"]
    assert {snapshot.outcome_side for snapshot in asian} == {"home", "away"}
    assert {snapshot.market_line for snapshot in asian} == {Decimal("-0.25")}
    totals = [snapshot for snapshot in snapshots if snapshot.market_type == "total_goals"]
    assert {snapshot.outcome_side for snapshot in totals} == {"over", "under"}
    assert {snapshot.market_line for snapshot in totals} == {Decimal("2.5")}
    assert {snapshot.snapshot_time for snapshot in snapshots} == {
        datetime(2026, 6, 26, 18, 45, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 6, 26, 18, 46, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 6, 26, 18, 47, tzinfo=ZoneInfo("UTC")),
    }


def test_map_the_odds_api_event_odds_ignores_non_pinnacle_bookmakers_and_incomplete_pairs():
    event = {
        "id": "event-2",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "bet365",
                "markets": [{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 2.10}]}],
            },
            {
                "key": "pinnacle",
                "last_update": "2026-06-26T18:45:00Z",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [{"name": "Arsenal", "price": 1.91, "point": -0.25}],
                    }
                ],
            },
        ],
    }

    assert map_the_odds_api_event_odds(match_id=42, event=event) == []


def test_map_the_odds_api_event_odds_can_override_snapshot_time_for_historical_queries():
    event = {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "pinnacle",
                "markets": [
                    {
                        "key": "h2h",
                        "last_update": "2026-06-26T18:50:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Draw", "price": 3.30},
                            {"name": "Chelsea", "price": 3.40},
                        ],
                    },
                ],
            }
        ],
    }

    snapshots = map_the_odds_api_event_odds(
        match_id=42,
        event=event,
        snapshot_time_override=datetime(2026, 6, 26, 18, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert len(snapshots) == 3
    assert {snapshot.snapshot_time for snapshot in snapshots} == {
        datetime(2026, 6, 26, 18, 0, tzinfo=ZoneInfo("UTC")),
    }


def test_map_the_odds_api_event_odds_maps_alternate_lines():
    event = {
        "id": "event-1",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "pinnacle",
                "markets": [
                    {
                        "key": "alternate_spreads",
                        "last_update": "2026-06-26T18:50:00Z",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.80, "point": -0.5},
                            {"name": "Chelsea", "price": 2.10, "point": 0.5},
                            {"name": "Arsenal", "price": 2.20, "point": -0.75},
                            {"name": "Chelsea", "price": 1.70, "point": 0.75},
                        ],
                    },
                    {
                        "key": "alternate_totals",
                        "last_update": "2026-06-26T18:50:00Z",
                        "outcomes": [
                            {"name": "Over", "price": 1.70, "point": 2.25},
                            {"name": "Under", "price": 2.20, "point": 2.25},
                            {"name": "Over", "price": 2.10, "point": 2.75},
                            {"name": "Under", "price": 1.80, "point": 2.75},
                        ],
                    },
                ],
            }
        ],
    }

    snapshots = map_the_odds_api_event_odds(match_id=42, event=event)

    assert {
        (snapshot.market_type, snapshot.market_line, snapshot.outcome_side)
        for snapshot in snapshots
    } == {
        ("asian_handicap", Decimal("-0.5"), "home"),
        ("asian_handicap", Decimal("-0.5"), "away"),
        ("asian_handicap", Decimal("-0.75"), "home"),
        ("asian_handicap", Decimal("-0.75"), "away"),
        ("total_goals", Decimal("2.25"), "over"),
        ("total_goals", Decimal("2.25"), "under"),
        ("total_goals", Decimal("2.75"), "over"),
        ("total_goals", Decimal("2.75"), "under"),
    }

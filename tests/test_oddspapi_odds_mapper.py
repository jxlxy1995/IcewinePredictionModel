from decimal import Decimal

from icewine_prediction.sources.oddspapi_odds_mapper import map_historical_odds


def test_map_historical_odds_keeps_selected_bookmakers_fulltime_handicap_and_totals():
    payload = [
        {
            "bookmaker": "pinnacle",
            "timestamp": "2026-05-23T18:00:00Z",
            "markets": [
                {
                    "marketId": 1070,
                    "marketName": "Asian Handicap",
                    "marketType": "spreads",
                    "period": "fulltime",
                    "handicap": -0.25,
                    "outcomes": [
                        {"name": "Mallorca", "price": 1.91, "side": "home"},
                        {"name": "Oviedo", "price": 1.99, "side": "away"},
                    ],
                },
                {
                    "marketId": 10170,
                    "marketName": "Over Under Full Time",
                    "marketType": "totals",
                    "period": "fulltime",
                    "handicap": 2.25,
                    "outcomes": [
                        {"name": "Over", "price": 1.88},
                        {"name": "Under", "price": 2.02},
                    ],
                },
                {
                    "marketId": 999,
                    "marketName": "First Half Asian Handicap",
                    "marketType": "spreads",
                    "period": "1sthalf",
                    "handicap": -0.25,
                    "outcomes": [{"name": "Mallorca", "price": 1.90, "side": "home"}],
                },
            ],
        },
        {
            "bookmaker": "unwanted",
            "timestamp": "2026-05-23T18:00:00Z",
            "markets": [
                {
                    "marketId": 1070,
                    "marketName": "Asian Handicap",
                    "marketType": "spreads",
                    "period": "fulltime",
                    "handicap": -0.25,
                    "outcomes": [{"name": "Mallorca", "price": 1.91, "side": "home"}],
                }
            ],
        },
    ]

    snapshots = map_historical_odds(
        payload,
        match_id=42,
        source_fixture_id="oddspapi-fixture",
    )

    assert len(snapshots) == 4
    assert {snapshot.bookmaker for snapshot in snapshots} == {"pinnacle"}
    assert {snapshot.market_type for snapshot in snapshots} == {
        "asian_handicap",
        "total_goals",
    }
    assert snapshots[0].match_id == 42
    assert snapshots[0].source_fixture_id == "oddspapi-fixture"
    assert snapshots[0].market_line == Decimal("-0.25")
    assert snapshots[0].outcome_side == "home"
    assert snapshots[0].odds == Decimal("1.91")
    assert snapshots[2].market_line == Decimal("2.25")
    assert {snapshots[2].outcome_side, snapshots[3].outcome_side} == {"over", "under"}

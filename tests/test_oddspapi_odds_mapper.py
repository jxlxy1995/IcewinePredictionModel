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
            "bookmaker": "sbobet",
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


def test_map_historical_odds_defaults_to_pinnacle_only_for_nested_payloads():
    payload = {
        "fixtureId": "oddspapi-fixture",
        "bookmakers": {
            "pinnacle": {
                "markets": {
                    "1070": {
                        "outcomes": {
                            "1070": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.91,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            },
            "sbobet": {
                "markets": {
                    "1070": {
                        "outcomes": {
                            "1070": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.88,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            },
        },
    }
    markets = [
        {
            "marketId": 1070,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": -0.25,
            "period": "fulltime",
            "outcomes": [{"outcomeId": 1070, "outcomeName": "1"}],
        },
    ]

    snapshots = map_historical_odds(
        payload,
        match_id=42,
        source_fixture_id="oddspapi-fixture",
        market_definitions=markets,
    )

    assert len(snapshots) == 1
    assert snapshots[0].bookmaker == "pinnacle"


def test_map_historical_odds_can_select_sbobet_for_nested_payloads():
    payload = {
        "fixtureId": "oddspapi-fixture",
        "bookmakers": {
            "pinnacle": {
                "markets": {
                    "1070": {
                        "outcomes": {
                            "1070": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.91,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            },
            "sbobet": {
                "markets": {
                    "1070": {
                        "outcomes": {
                            "1070": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.88,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            },
        },
    }
    markets = [
        {
            "marketId": 1070,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": -0.25,
            "period": "fulltime",
            "outcomes": [{"outcomeId": 1070, "outcomeName": "1"}],
        },
    ]

    snapshots = map_historical_odds(
        payload,
        match_id=42,
        source_fixture_id="oddspapi-fixture",
        selected_bookmakers={"sbobet"},
        market_definitions=markets,
    )

    assert len(snapshots) == 1
    assert snapshots[0].bookmaker == "sbobet"
    assert snapshots[0].odds == Decimal("1.88")


def test_map_historical_odds_handles_nested_oddspapi_response_with_market_definitions():
    payload = {
        "fixtureId": "oddspapi-fixture",
        "bookmakers": {
            "pinnacle": {
                "markets": {
                    "1070": {
                        "outcomes": {
                            "1070": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.91,
                                        }
                                    ]
                                }
                            },
                            "1071": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 1.99,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                    "10170": {
                        "outcomes": {
                            "10170": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:05:00Z",
                                            "price": 1.88,
                                        }
                                    ]
                                }
                            },
                            "10171": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:05:00Z",
                                            "price": 2.02,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    markets = [
        {
            "marketId": 1070,
            "marketName": "Asian Handicap",
            "marketType": "spreads",
            "handicap": -0.25,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 1070, "outcomeName": "1"},
                {"outcomeId": 1071, "outcomeName": "2"},
            ],
        },
        {
            "marketId": 10170,
            "marketName": "Over Under Full Time",
            "marketType": "totals",
            "handicap": 2.25,
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 10170, "outcomeName": "Over"},
                {"outcomeId": 10171, "outcomeName": "Under"},
            ],
        },
    ]

    snapshots = map_historical_odds(
        payload,
        match_id=42,
        source_fixture_id="oddspapi-fixture",
        market_definitions=markets,
    )

    assert len(snapshots) == 4
    assert {snapshot.market_type for snapshot in snapshots} == {
        "asian_handicap",
        "total_goals",
    }
    assert {snapshot.outcome_side for snapshot in snapshots} == {
        "home",
        "away",
        "over",
        "under",
    }
    assert snapshots[0].snapshot_time.isoformat() == "2026-05-23T18:00:00+00:00"


def test_map_historical_odds_handles_nested_match_winner_response():
    payload = {
        "fixtureId": "oddspapi-fixture",
        "bookmakers": {
            "pinnacle": {
                "markets": {
                    "9001": {
                        "outcomes": {
                            "9001": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 2.10,
                                        }
                                    ]
                                }
                            },
                            "9002": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 3.25,
                                        }
                                    ]
                                }
                            },
                            "9003": {
                                "players": {
                                    "0": [
                                        {
                                            "createdAt": "2026-05-23T18:00:00Z",
                                            "price": 3.60,
                                        }
                                    ]
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    markets = [
        {
            "marketId": 9001,
            "marketName": "1X2 Full Time",
            "marketType": "moneyline",
            "period": "fulltime",
            "outcomes": [
                {"outcomeId": 9001, "outcomeName": "1"},
                {"outcomeId": 9002, "outcomeName": "X"},
                {"outcomeId": 9003, "outcomeName": "2"},
            ],
        },
    ]

    snapshots = map_historical_odds(
        payload,
        match_id=42,
        source_fixture_id="oddspapi-fixture",
        market_definitions=markets,
    )

    assert len(snapshots) == 3
    assert {snapshot.market_type for snapshot in snapshots} == {"match_winner"}
    assert {snapshot.market_line for snapshot in snapshots} == {Decimal("0")}
    assert {snapshot.outcome_side for snapshot in snapshots} == {"home", "draw", "away"}

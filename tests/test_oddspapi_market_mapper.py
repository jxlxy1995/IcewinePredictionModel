from decimal import Decimal

from icewine_prediction.sources.oddspapi_market_mapper import map_markets


def test_map_markets_keeps_fulltime_asian_handicap_and_total_lines():
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
        {
            "marketId": 999,
            "marketName": "First Half Asian Handicap",
            "marketType": "spreads",
            "handicap": -0.25,
            "period": "1sthalf",
        },
        {
            "marketId": 1000,
            "marketName": "Bad Line",
            "marketType": "totals",
            "handicap": 2.33,
            "period": "fulltime",
        },
    ]

    mapped = map_markets(markets)

    assert [market.market_id for market in mapped] == ["1070", "10170"]
    assert mapped[0].market_type == "asian_handicap"
    assert mapped[0].line == Decimal("-0.25")
    assert mapped[0].outcome_ids == ("1070", "1071")
    assert mapped[1].market_type == "total_goals"
    assert mapped[1].line == Decimal("2.25")
    assert mapped[1].outcome_ids == ("10170", "10171")

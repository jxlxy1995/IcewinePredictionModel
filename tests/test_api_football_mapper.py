import json
from decimal import Decimal
from pathlib import Path

from icewine_prediction.sources.api_football_mapper import map_fixtures, map_odds_snapshots


def test_map_fixtures_converts_api_response():
    payload = json.loads(
        Path("tests/fixtures/api_football/fixtures.json").read_text(encoding="utf-8")
    )

    fixtures = map_fixtures(payload)

    assert len(fixtures) == 1
    assert fixtures[0].source_match_id == "1001"
    assert fixtures[0].league_name == "Premier League"
    assert fixtures[0].home_team_name == "Manchester City"
    assert fixtures[0].away_team_name == "Arsenal"
    assert fixtures[0].status == "scheduled"


def test_map_odds_snapshots_extracts_asian_handicap_and_total_line():
    payload = json.loads(Path("tests/fixtures/api_football/odds.json").read_text(encoding="utf-8"))

    snapshots = map_odds_snapshots(payload)

    assert len(snapshots) == 1
    assert snapshots[0].source_match_id == "1001"
    assert snapshots[0].bookmaker == "Sample Bookmaker"
    assert snapshots[0].asian_handicap == Decimal("-0.25")
    assert snapshots[0].home_odds == Decimal("1.92")
    assert snapshots[0].away_odds == Decimal("1.96")
    assert snapshots[0].total_line == Decimal("2.5")
    assert snapshots[0].over_odds == Decimal("1.94")
    assert snapshots[0].under_odds == Decimal("1.94")


def test_map_odds_snapshots_pairs_same_market_line_and_selects_balanced_line():
    payload = {
        "response": [
            {
                "fixture": {"id": 1001},
                "bookmakers": [
                    {
                        "name": "Bet365",
                        "bets": [
                            {
                                "name": "Asian Handicap",
                                "values": [
                                    {"value": "Home -1.25", "odd": "5.50"},
                                    {"value": "Away -1.25", "odd": "1.15"},
                                    {"value": "Home +0", "odd": "2.25"},
                                    {"value": "Away +0", "odd": "1.62"},
                                    {"value": "Home +0.25", "odd": "1.98"},
                                    {"value": "Away +0.25", "odd": "1.88"},
                                    {"value": "Home +1.5", "odd": "1.24"},
                                    {"value": "Away +1.5", "odd": "3.90"},
                                ],
                            },
                            {
                                "name": "Goals Over/Under",
                                "values": [
                                    {"value": "Over 1.5", "odd": "1.17"},
                                    {"value": "Under 1.5", "odd": "5.00"},
                                    {"value": "Over 2.5", "odd": "1.57"},
                                    {"value": "Under 2.5", "odd": "2.38"},
                                    {"value": "Over 3.0", "odd": "1.95"},
                                    {"value": "Under 3.0", "odd": "1.79"},
                                    {"value": "Over 4.5", "odd": "4.33"},
                                    {"value": "Under 4.5", "odd": "1.22"},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    snapshots = map_odds_snapshots(payload)

    assert len(snapshots) == 1
    assert snapshots[0].asian_handicap == Decimal("0.25")
    assert snapshots[0].home_odds == Decimal("1.98")
    assert snapshots[0].away_odds == Decimal("1.88")
    assert snapshots[0].total_line == Decimal("3.0")
    assert snapshots[0].over_odds == Decimal("1.95")
    assert snapshots[0].under_odds == Decimal("1.79")


def test_map_odds_snapshots_ignores_non_standard_market_lines():
    payload = {
        "response": [
            {
                "fixture": {"id": 1001},
                "bookmakers": [
                    {
                        "name": "Bet365",
                        "bets": [
                            {
                                "name": "Asian Handicap",
                                "values": [
                                    {"value": "Home -0.80", "odd": "1.90"},
                                    {"value": "Away -0.80", "odd": "1.90"},
                                    {"value": "Home -0.75", "odd": "1.82"},
                                    {"value": "Away -0.75", "odd": "2.02"},
                                ],
                            },
                            {
                                "name": "Goals Over/Under",
                                "values": [
                                    {"value": "Over 2.63", "odd": "1.90"},
                                    {"value": "Under 2.63", "odd": "1.90"},
                                    {"value": "Over 2.75", "odd": "1.86"},
                                    {"value": "Under 2.75", "odd": "2.04"},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    snapshots = map_odds_snapshots(payload)

    assert len(snapshots) == 1
    assert snapshots[0].asian_handicap == Decimal("-0.75")
    assert snapshots[0].total_line == Decimal("2.75")

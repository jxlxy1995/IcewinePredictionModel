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

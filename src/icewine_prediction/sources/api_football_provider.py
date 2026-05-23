from datetime import date, timedelta

from icewine_prediction.settings import LeagueSettings
from icewine_prediction.sources.api_football_mapper import (
    ExternalFixture,
    ExternalOddsSnapshot,
    map_fixtures,
    map_odds_snapshots,
)
from icewine_prediction.time_utils import now_beijing


class ApiFootballProvider:
    def __init__(self, client) -> None:
        self.client = client

    def fetch_upcoming_fixtures(
        self,
        leagues: list[LeagueSettings],
        days: int,
    ) -> list[ExternalFixture]:
        today = now_beijing().date()
        to_date = today + timedelta(days=days)
        fixtures: list[ExternalFixture] = []
        for league in leagues:
            if not league.enabled:
                continue
            payload = self.client.get(
                "fixtures",
                {
                    "league": league.api_football_id,
                    "from": today.isoformat(),
                    "to": to_date.isoformat(),
                },
            )
            fixtures.extend(map_fixtures(payload))
        return fixtures

    def fetch_results(
        self,
        leagues: list[LeagueSettings],
        from_date: date,
        to_date: date,
    ) -> list[ExternalFixture]:
        fixtures: list[ExternalFixture] = []
        for league in leagues:
            if not league.enabled:
                continue
            payload = self.client.get(
                "fixtures",
                {
                    "league": league.api_football_id,
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat(),
                    "status": "FT",
                },
            )
            fixtures.extend(map_fixtures(payload))
        return fixtures

    def fetch_odds_for_fixtures(self, fixture_ids: list[str]) -> list[ExternalOddsSnapshot]:
        snapshots: list[ExternalOddsSnapshot] = []
        for fixture_id in fixture_ids:
            payload = self.client.get("odds", {"fixture": fixture_id})
            snapshots.extend(map_odds_snapshots(payload))
        return snapshots

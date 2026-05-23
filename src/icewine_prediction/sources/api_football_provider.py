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
        enabled_league_ids = {
            str(league.api_football_id)
            for league in leagues
            if league.enabled
        }
        fixtures: list[ExternalFixture] = []
        seen_match_ids: set[str] = set()
        for offset in range(days + 1):
            query_date = today + timedelta(days=offset)
            payload = self.client.get(
                "fixtures",
                {
                    "date": query_date.isoformat(),
                    "timezone": "Asia/Shanghai",
                },
            )
            for fixture in map_fixtures(payload):
                if fixture.source_league_id not in enabled_league_ids:
                    continue
                if fixture.source_match_id in seen_match_ids:
                    continue
                seen_match_ids.add(fixture.source_match_id)
                fixtures.append(fixture)
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

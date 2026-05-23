from icewine_prediction.settings import LeagueSettings
from icewine_prediction.sources.api_football_provider import ApiFootballProvider


class FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint == "fixtures":
            return {
                "response": [
                    {
                        "fixture": {
                            "id": 1001,
                            "date": "2026-05-23T22:00:00+08:00",
                            "status": {"short": "NS"},
                        },
                        "league": {"id": 39, "name": "Premier League", "country": "England"},
                        "teams": {
                            "home": {"id": 50, "name": "Manchester City"},
                            "away": {"id": 42, "name": "Arsenal"},
                        },
                        "goals": {"home": None, "away": None},
                    }
                ]
            }
        return {"response": []}


def test_provider_fetches_upcoming_fixtures_for_enabled_leagues():
    provider = ApiFootballProvider(FakeClient())
    leagues = [LeagueSettings("Premier League", "England", 39, True, 100)]

    fixtures = provider.fetch_upcoming_fixtures(leagues, days=3)

    assert len(fixtures) == 1
    assert fixtures[0].source_match_id == "1001"
    assert provider.client.calls[0][0] == "fixtures"
    assert "date" in provider.client.calls[0][1]
    assert provider.client.calls[0][1]["timezone"] == "Asia/Shanghai"
    assert "league" not in provider.client.calls[0][1]


def test_provider_filters_date_query_results_to_enabled_leagues():
    class MixedLeagueClient:
        def get(self, endpoint, params):
            return {
                "response": [
                    {
                        "fixture": {
                            "id": 1001,
                            "date": "2026-05-24T00:00:00+08:00",
                            "status": {"short": "NS"},
                        },
                        "league": {"id": 135, "name": "Serie A", "country": "Italy"},
                        "teams": {
                            "home": {"id": 500, "name": "Bologna"},
                            "away": {"id": 505, "name": "Inter"},
                        },
                        "goals": {"home": None, "away": None},
                    },
                    {
                        "fixture": {
                            "id": 2001,
                            "date": "2026-05-24T03:00:00+08:00",
                            "status": {"short": "NS"},
                        },
                        "league": {"id": 999, "name": "Untracked League", "country": "Nowhere"},
                        "teams": {
                            "home": {"id": 1, "name": "A"},
                            "away": {"id": 2, "name": "B"},
                        },
                        "goals": {"home": None, "away": None},
                    },
                ]
            }

    provider = ApiFootballProvider(MixedLeagueClient())
    leagues = [LeagueSettings("Serie A", "Italy", 135, True, 95)]

    fixtures = provider.fetch_upcoming_fixtures(leagues, days=1)

    assert len(fixtures) == 1
    assert fixtures[0].league_name == "Serie A"
    assert fixtures[0].home_team_name == "Bologna"


def test_provider_fetches_historical_fixtures_by_league_and_season():
    class HistoricalClient:
        def __init__(self):
            self.calls = []

        def get(self, endpoint, params):
            self.calls.append((endpoint, params))
            return {
                "response": [
                    {
                        "fixture": {
                            "id": 3001,
                            "date": "2025-05-25T03:00:00+08:00",
                            "status": {"short": "FT"},
                        },
                        "league": {"id": 140, "name": "La Liga", "country": "Spain"},
                        "teams": {
                            "home": {"id": 541, "name": "Real Madrid"},
                            "away": {"id": 529, "name": "Barcelona"},
                        },
                        "goals": {"home": 2, "away": 1},
                    }
                ]
            }

    client = HistoricalClient()
    provider = ApiFootballProvider(client)

    fixtures = provider.fetch_historical_fixtures(league_id=140, season=2024)

    assert fixtures[0].source_match_id == "3001"
    assert fixtures[0].status == "finished"
    assert fixtures[0].home_score == 2
    assert client.calls == [
        (
            "fixtures",
            {
                "league": 140,
                "season": 2024,
                "timezone": "Asia/Shanghai",
            },
        )
    ]

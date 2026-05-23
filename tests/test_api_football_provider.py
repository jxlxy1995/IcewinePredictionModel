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
                            "referee": "Example Referee",
                            "timezone": "Asia/Shanghai",
                            "date": "2025-05-25T03:00:00+08:00",
                            "timestamp": 1748113200,
                            "periods": {"first": 1748113200, "second": 1748116800},
                            "venue": {
                                "id": 1460,
                                "name": "Santiago Bernabeu",
                                "city": "Madrid",
                            },
                            "status": {"long": "Match Finished", "short": "FT", "elapsed": 90, "extra": 4},
                        },
                        "league": {
                            "id": 140,
                            "name": "La Liga",
                            "country": "Spain",
                            "logo": "https://media.api-sports.io/football/leagues/140.png",
                            "flag": "https://media.api-sports.io/flags/es.svg",
                            "season": 2024,
                            "round": "Regular Season - 38",
                            "standings": True,
                        },
                        "teams": {
                            "home": {
                                "id": 541,
                                "name": "Real Madrid",
                                "logo": "https://media.api-sports.io/football/teams/541.png",
                                "winner": True,
                            },
                            "away": {
                                "id": 529,
                                "name": "Barcelona",
                                "logo": "https://media.api-sports.io/football/teams/529.png",
                                "winner": False,
                            },
                        },
                        "goals": {"home": 2, "away": 1},
                        "score": {
                            "halftime": {"home": 1, "away": 0},
                            "fulltime": {"home": 2, "away": 1},
                            "extratime": {"home": None, "away": None},
                            "penalty": {"home": None, "away": None},
                        },
                    }
                ]
            }

    client = HistoricalClient()
    provider = ApiFootballProvider(client)

    fixtures = provider.fetch_historical_fixtures(league_id=140, season=2024)

    assert fixtures[0].source_match_id == "3001"
    assert fixtures[0].status == "finished"
    assert fixtures[0].home_score == 2
    assert fixtures[0].season == 2024
    assert fixtures[0].league_round == "Regular Season - 38"
    assert fixtures[0].venue_name == "Santiago Bernabeu"
    assert fixtures[0].halftime_home_score == 1
    assert fixtures[0].home_team_logo_url.endswith("/541.png")
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

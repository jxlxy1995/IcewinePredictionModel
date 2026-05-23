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

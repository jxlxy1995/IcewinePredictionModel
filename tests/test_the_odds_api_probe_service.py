from icewine_prediction.the_odds_api_probe_service import (
    TheOddsApiProbeRequest,
    build_the_odds_api_upcoming_coverage_report_with_client,
    build_the_odds_api_sports_report_with_client,
    build_the_odds_api_probe_report_with_client,
)
from icewine_prediction.sources.the_odds_api_client import TheOddsApiApiError


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.request_count = 0

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        self.request_count += 1
        return self.payload


class FakeEndpointClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.request_count = 0

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        self.request_count += 1
        payload = self.payloads[endpoint]
        if isinstance(payload, Exception):
            raise payload
        return self.payloads[endpoint]


def test_probe_report_summarizes_pinnacle_three_market_coverage():
    client = FakeClient(
        [
            {
                "id": "event-1",
                "sport_key": "soccer_epl",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "commence_time": "2026-06-26T19:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [
                            {"key": "h2h", "outcomes": [{"name": "Arsenal"}, {"name": "Draw"}, {"name": "Chelsea"}]},
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Arsenal", "price": 1.91, "point": -0.25},
                                    {"name": "Chelsea", "price": 1.99, "point": 0.25},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": 1.88, "point": 2.5},
                                    {"name": "Under", "price": 2.02, "point": 2.5},
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "id": "event-2",
                "sport_key": "soccer_epl",
                "home_team": "Liverpool",
                "away_team": "Everton",
                "commence_time": "2026-06-27T19:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [{"key": "h2h", "outcomes": []}],
                    }
                ],
            },
        ]
    )

    report = build_the_odds_api_probe_report_with_client(
        client,
        TheOddsApiProbeRequest(sport_key="soccer_epl", max_events=10),
    )

    assert client.calls == [
        (
            "sports/soccer_epl/odds",
            {
                "regions": "eu",
                "bookmakers": "pinnacle",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
    ]
    assert report.event_count == 2
    assert report.pinnacle_event_count == 2
    assert report.full_three_market_count == 1
    assert report.market_counts == {"h2h": 2, "spreads": 1, "totals": 1}
    assert "The Odds API Pinnacle Probe" in report.to_text()
    assert "full_three_market=1/2" in report.to_text()
    assert "Arsenal vs Chelsea" in report.to_text()


def test_probe_report_limits_displayed_events_after_fetch():
    client = FakeClient(
        [
            {
                "id": "event-1",
                "sport_key": "soccer_epl",
                "home_team": "A",
                "away_team": "B",
                "bookmakers": [],
            },
            {
                "id": "event-2",
                "sport_key": "soccer_epl",
                "home_team": "C",
                "away_team": "D",
                "bookmakers": [],
            },
        ]
    )

    report = build_the_odds_api_probe_report_with_client(
        client,
        TheOddsApiProbeRequest(sport_key="soccer_epl", max_events=1),
    )

    assert report.event_count == 1
    assert "returned_events=1" in report.to_text()


def test_probe_report_escapes_non_ascii_team_names_for_windows_console():
    client = FakeClient(
        [
            {
                "id": "event-1",
                "sport_key": "soccer_sweden_allsvenskan",
                "home_team": "IFK Göteborg",
                "away_team": "Malmö FF",
                "commence_time": "2026-06-28T13:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "markets": [{"key": "h2h", "outcomes": []}],
                    }
                ],
            }
        ]
    )

    report = build_the_odds_api_probe_report_with_client(
        client,
        TheOddsApiProbeRequest(sport_key="soccer_sweden_allsvenskan", max_events=10),
    )

    text = report.to_text()

    assert "IFK G\\xf6teborg vs Malm\\xf6 FF" in text
    assert text.isascii()


def test_sports_report_lists_soccer_keys():
    client = FakeClient(
        [
            {"key": "americanfootball_nfl", "title": "NFL", "active": True},
            {"key": "soccer_epl", "title": "EPL", "active": True},
            {"key": "soccer_sweden_allsvenskan", "title": "Allsvenskan", "active": True},
        ]
    )

    text = build_the_odds_api_sports_report_with_client(client, key_prefix="soccer_")

    assert client.calls == [("sports", {})]
    assert "The Odds API Sports" in text
    assert "soccer_epl | EPL | active=True" in text
    assert "soccer_sweden_allsvenskan | Allsvenskan | active=True" in text
    assert "americanfootball_nfl" not in text


def test_upcoming_coverage_report_summarizes_multiple_sports_without_writes():
    client = FakeEndpointClient(
        {
            "sports/soccer_epl/odds": [
                {
                    "id": "event-1",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "commence_time": "2026-06-26T19:00:00Z",
                    "bookmakers": [
                        {
                            "key": "pinnacle",
                            "markets": [
                                {"key": "h2h", "outcomes": []},
                                {"key": "spreads", "outcomes": []},
                                {"key": "totals", "outcomes": []},
                            ],
                        }
                    ],
                }
            ],
            "sports/soccer_sweden_allsvenskan/odds": [
                {
                    "id": "event-2",
                    "home_team": "A",
                    "away_team": "B",
                    "commence_time": "2026-06-27T19:00:00Z",
                    "bookmakers": [],
                }
            ],
        }
    )

    report = build_the_odds_api_upcoming_coverage_report_with_client(
        client,
        sport_keys=("soccer_epl", "soccer_sweden_allsvenskan"),
        max_events_per_sport=5,
    )

    assert client.calls == [
        (
            "sports/soccer_epl/odds",
            {
                "regions": "eu",
                "bookmakers": "pinnacle",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        ),
        (
            "sports/soccer_sweden_allsvenskan/odds",
            {
                "regions": "eu",
                "bookmakers": "pinnacle",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        ),
    ]
    assert "The Odds API Upcoming Coverage" in report
    assert "soccer_epl events=1 pinnacle=1 full_three_market=1/1" in report
    assert "soccer_sweden_allsvenskan events=1 pinnacle=0 full_three_market=0/1" in report
    assert "TOTAL sports=2 events=2 pinnacle=1 full_three_market=1/2 requests_used=2" in report


def test_upcoming_coverage_report_continues_when_one_sport_errors():
    client = FakeEndpointClient(
        {
            "sports/soccer_epl/odds": [
                {
                    "id": "event-1",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "bookmakers": [
                        {
                            "key": "pinnacle",
                            "markets": [
                                {"key": "h2h", "outcomes": []},
                                {"key": "spreads", "outcomes": []},
                                {"key": "totals", "outcomes": []},
                            ],
                        }
                    ],
                }
            ],
            "sports/soccer_spain_la_liga/odds": TheOddsApiApiError(
                "The Odds API HTTP error: HTTPError",
                status_code=422,
            ),
        }
    )

    report = build_the_odds_api_upcoming_coverage_report_with_client(
        client,
        sport_keys=("soccer_epl", "soccer_spain_la_liga"),
        max_events_per_sport=5,
    )

    assert "soccer_epl events=1 pinnacle=1 full_three_market=1/1" in report
    assert "soccer_spain_la_liga ERROR status=422" in report
    assert "TOTAL sports=2 events=1 pinnacle=1 full_three_market=1/1 requests_used=2" in report

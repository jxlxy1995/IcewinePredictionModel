from dataclasses import dataclass
from typing import Any

from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.the_odds_api_client import TheOddsApiApiError, TheOddsApiClient


DEFAULT_MARKETS = ("h2h", "spreads", "totals")
DEFAULT_BOOKMAKER = "pinnacle"
DEFAULT_REGION = "eu"


@dataclass(frozen=True)
class TheOddsApiProbeRequest:
    sport_key: str
    max_events: int = 10
    bookmaker: str = DEFAULT_BOOKMAKER
    region: str = DEFAULT_REGION
    markets: tuple[str, ...] = DEFAULT_MARKETS


@dataclass(frozen=True)
class TheOddsApiEventProbe:
    event_id: str
    home_team: str
    away_team: str
    commence_time: str
    market_keys: tuple[str, ...]

    @property
    def has_full_three_markets(self) -> bool:
        return set(DEFAULT_MARKETS).issubset(self.market_keys)


@dataclass(frozen=True)
class TheOddsApiProbeReport:
    sport_key: str
    bookmaker: str
    region: str
    requested_markets: tuple[str, ...]
    event_count: int
    pinnacle_event_count: int
    full_three_market_count: int
    market_counts: dict[str, int]
    request_count: int
    events: tuple[TheOddsApiEventProbe, ...]

    def to_text(self) -> str:
        lines = [
            "The Odds API Pinnacle Probe",
            (
                f"sport={self.sport_key} bookmaker={self.bookmaker} region={self.region} "
                f"markets={','.join(self.requested_markets)}"
            ),
            (
                f"returned_events={self.event_count} pinnacle_events={self.pinnacle_event_count} "
                f"full_three_market={self.full_three_market_count}/{self.event_count}"
            ),
            (
                "market_counts "
                + " ".join(
                    f"{market}={self.market_counts.get(market, 0)}"
                    for market in self.requested_markets
                )
            ),
            f"requests_used={self.request_count}",
        ]
        if self.events:
            lines.append("events:")
            for event in self.events:
                markets = ",".join(event.market_keys) if event.market_keys else "none"
                lines.append(
                    f"- {event.commence_time} {_ascii_text(event.home_team)} "
                    f"vs {_ascii_text(event.away_team)}: {markets}"
                )
        return "\n".join(lines)


def build_the_odds_api_probe_report(
    *,
    sport_key: str,
    max_events: int = 10,
    request_budget: int = 5,
    timeout_seconds: int = 20,
    bookmaker: str = DEFAULT_BOOKMAKER,
    region: str = DEFAULT_REGION,
) -> str:
    settings = load_project_settings()
    client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    report = build_the_odds_api_probe_report_with_client(
        client,
        TheOddsApiProbeRequest(
            sport_key=sport_key,
            max_events=max_events,
            bookmaker=bookmaker,
            region=region,
        ),
    )
    return report.to_text()


def build_the_odds_api_sports_report(
    *,
    key_prefix: str = "soccer_",
    request_budget: int = 2,
    timeout_seconds: int = 20,
) -> str:
    settings = load_project_settings()
    client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    return build_the_odds_api_sports_report_with_client(client, key_prefix=key_prefix)


def build_the_odds_api_sports_report_with_client(client: Any, *, key_prefix: str = "") -> str:
    payload = client.get("sports", {})
    sports = [
        item
        for item in (payload if isinstance(payload, list) else [])
        if str(item.get("key", "")).startswith(key_prefix)
    ]
    lines = [
        "The Odds API Sports",
        f"key_prefix={key_prefix} returned={len(sports)} requests_used={client.request_count}",
    ]
    for item in sports:
        lines.append(
            f"{_ascii_text(str(item.get('key', '')))} | "
            f"{_ascii_text(str(item.get('title', '')))} | "
            f"active={item.get('active')}"
        )
    return "\n".join(lines)


def build_the_odds_api_upcoming_coverage_report(
    *,
    sport_keys: tuple[str, ...],
    max_events_per_sport: int = 10,
    request_budget: int = 30,
    timeout_seconds: int = 20,
    bookmaker: str = DEFAULT_BOOKMAKER,
    region: str = DEFAULT_REGION,
) -> str:
    settings = load_project_settings()
    client = TheOddsApiClient(
        api_key=settings.the_odds_api_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    return build_the_odds_api_upcoming_coverage_report_with_client(
        client,
        sport_keys=sport_keys,
        max_events_per_sport=max_events_per_sport,
        bookmaker=bookmaker,
        region=region,
    )


def build_the_odds_api_upcoming_coverage_report_with_client(
    client: Any,
    *,
    sport_keys: tuple[str, ...],
    max_events_per_sport: int = 10,
    bookmaker: str = DEFAULT_BOOKMAKER,
    region: str = DEFAULT_REGION,
) -> str:
    reports: list[TheOddsApiProbeReport] = []
    errors: list[tuple[str, TheOddsApiApiError]] = []
    for sport_key in sport_keys:
        try:
            reports.append(
                build_the_odds_api_probe_report_with_client(
                    client,
                    TheOddsApiProbeRequest(
                        sport_key=sport_key,
                        max_events=max_events_per_sport,
                        bookmaker=bookmaker,
                        region=region,
                    ),
                )
            )
        except TheOddsApiApiError as exc:
            errors.append((sport_key, exc))
    lines = [
        "The Odds API Upcoming Coverage",
        f"bookmaker={bookmaker} region={region} sports={len(sport_keys)}",
    ]
    total_events = 0
    total_pinnacle = 0
    total_full = 0
    for report in reports:
        total_events += report.event_count
        total_pinnacle += report.pinnacle_event_count
        total_full += report.full_three_market_count
        lines.append(
            f"{report.sport_key} events={report.event_count} "
            f"pinnacle={report.pinnacle_event_count} "
            f"full_three_market={report.full_three_market_count}/{report.event_count} "
            + " ".join(
                f"{market}={report.market_counts.get(market, 0)}"
                for market in report.requested_markets
            )
        )
    for sport_key, exc in errors:
        status = exc.status_code if exc.status_code is not None else "unknown"
        lines.append(f"{sport_key} ERROR status={status} message={_ascii_text(str(exc))}")
    lines.append(
        f"TOTAL sports={len(sport_keys)} events={total_events} pinnacle={total_pinnacle} "
        f"full_three_market={total_full}/{total_events} requests_used={client.request_count}"
    )
    return "\n".join(lines)


def build_the_odds_api_probe_report_with_client(
    client: Any,
    request: TheOddsApiProbeRequest,
) -> TheOddsApiProbeReport:
    payload = client.get(
        f"sports/{request.sport_key}/odds",
        {
            "regions": request.region,
            "bookmakers": request.bookmaker,
            "markets": ",".join(request.markets),
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
    )
    raw_events = list(payload if isinstance(payload, list) else [])
    raw_events = raw_events[: request.max_events]
    events = tuple(_summarize_event(event, request.bookmaker) for event in raw_events)
    market_counts = {
        market: sum(1 for event in events if market in event.market_keys)
        for market in request.markets
    }
    return TheOddsApiProbeReport(
        sport_key=request.sport_key,
        bookmaker=request.bookmaker,
        region=request.region,
        requested_markets=request.markets,
        event_count=len(events),
        pinnacle_event_count=sum(1 for event in events if event.market_keys),
        full_three_market_count=sum(1 for event in events if event.has_full_three_markets),
        market_counts=market_counts,
        request_count=getattr(client, "request_count", 0),
        events=events,
    )


def _summarize_event(event: dict[str, Any], bookmaker: str) -> TheOddsApiEventProbe:
    bookmaker_payload = _find_bookmaker(event.get("bookmakers") or [], bookmaker)
    markets = tuple(
        str(market.get("key"))
        for market in (bookmaker_payload.get("markets") if bookmaker_payload else []) or []
        if market.get("key")
    )
    return TheOddsApiEventProbe(
        event_id=str(event.get("id", "")),
        home_team=str(event.get("home_team", "")),
        away_team=str(event.get("away_team", "")),
        commence_time=str(event.get("commence_time", "")),
        market_keys=markets,
    )


def _find_bookmaker(bookmakers: list[dict[str, Any]], bookmaker: str) -> dict[str, Any] | None:
    for item in bookmakers:
        if str(item.get("key", "")).lower() == bookmaker.lower():
            return item
    return None


def _ascii_text(value: str) -> str:
    return value.encode("ascii", errors="backslashreplace").decode("ascii")

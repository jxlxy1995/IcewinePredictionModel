from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from icewine_prediction.feature_service import is_standard_market_line
from icewine_prediction.time_utils import now_beijing


SOURCE_NAME = "api_football"


@dataclass(frozen=True)
class ExternalFixture:
    source_name: str
    source_match_id: str
    source_league_id: str
    league_name: str
    country: str
    home_source_team_id: str
    home_team_name: str
    away_source_team_id: str
    away_team_name: str
    kickoff_time: datetime
    status: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class ExternalOddsSnapshot:
    source_name: str
    source_match_id: str
    captured_at: datetime
    bookmaker: str
    asian_handicap: Decimal | None
    home_odds: Decimal | None
    away_odds: Decimal | None
    total_line: Decimal | None
    over_odds: Decimal | None
    under_odds: Decimal | None


def _map_status(short_status: str) -> str:
    if short_status == "NS":
        return "scheduled"
    if short_status in {"FT", "AET", "PEN"}:
        return "finished"
    return short_status.lower()


def map_fixtures(payload: dict) -> list[ExternalFixture]:
    fixtures = []
    for item in payload.get("response", []):
        fixture = item["fixture"]
        league = item["league"]
        teams = item["teams"]
        goals = item.get("goals") or {}
        fixtures.append(
            ExternalFixture(
                source_name=SOURCE_NAME,
                source_match_id=str(fixture["id"]),
                source_league_id=str(league["id"]),
                league_name=league["name"],
                country=league["country"],
                home_source_team_id=str(teams["home"]["id"]),
                home_team_name=teams["home"]["name"],
                away_source_team_id=str(teams["away"]["id"]),
                away_team_name=teams["away"]["name"],
                kickoff_time=datetime.fromisoformat(fixture["date"]),
                status=_map_status(fixture["status"]["short"]),
                home_score=goals.get("home"),
                away_score=goals.get("away"),
            )
        )
    return fixtures


def _find_bet(bookmaker: dict, bet_name: str) -> dict | None:
    for bet in bookmaker.get("bets", []):
        if bet.get("name") == bet_name:
            return bet
    return None


def _parse_prefixed_decimal(value: str, prefix: str) -> Decimal | None:
    if not value.startswith(prefix):
        return None
    return Decimal(value.removeprefix(prefix).strip())


def _balanced_pair_score(first_odds: Decimal, second_odds: Decimal) -> tuple[Decimal, Decimal]:
    return abs(first_odds - second_odds), abs(((first_odds + second_odds) / Decimal("2")) - Decimal("2"))


def _select_balanced_line(
    lines: dict[Decimal, dict[str, Decimal]],
    first_key: str,
    second_key: str,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    candidates = [
        (line, odds[first_key], odds[second_key])
        for line, odds in lines.items()
        if first_key in odds and second_key in odds
    ]
    if not candidates:
        return None, None, None
    selected_line, first_odds, second_odds = min(
        candidates,
        key=lambda candidate: _balanced_pair_score(candidate[1], candidate[2]),
    )
    return selected_line, first_odds, second_odds


def _add_away_handicap_line(
    lines: dict[Decimal, dict[str, Decimal]],
    handicap: Decimal,
    odds: Decimal,
) -> None:
    if handicap in lines and "home" in lines[handicap]:
        lines[handicap]["away"] = odds
        return
    opposite_handicap = -handicap
    if opposite_handicap in lines and "home" in lines[opposite_handicap]:
        lines[opposite_handicap]["away"] = odds
        return
    lines.setdefault(handicap, {})["away"] = odds


def _extract_asian_handicap(bookmaker: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    bet = _find_bet(bookmaker, "Asian Handicap")
    if bet is None:
        return None, None, None
    lines: dict[Decimal, dict[str, Decimal]] = {}
    for value in bet.get("values", []):
        label = value["value"]
        if label.startswith("Home "):
            handicap = _parse_prefixed_decimal(label, "Home ")
            if handicap is not None and is_standard_market_line(handicap):
                lines.setdefault(handicap, {})["home"] = Decimal(value["odd"])
        elif label.startswith("Away "):
            handicap = _parse_prefixed_decimal(label, "Away ")
            if handicap is not None and is_standard_market_line(handicap):
                _add_away_handicap_line(lines, handicap, Decimal(value["odd"]))
    return _select_balanced_line(lines, "home", "away")


def _extract_total_line(bookmaker: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    bet = _find_bet(bookmaker, "Goals Over/Under")
    if bet is None:
        return None, None, None
    lines: dict[Decimal, dict[str, Decimal]] = {}
    for value in bet.get("values", []):
        label = value["value"]
        if label.startswith("Over "):
            total_line = _parse_prefixed_decimal(label, "Over ")
            if total_line is not None and is_standard_market_line(total_line):
                lines.setdefault(total_line, {})["over"] = Decimal(value["odd"])
        elif label.startswith("Under "):
            total_line = _parse_prefixed_decimal(label, "Under ")
            if total_line is not None and is_standard_market_line(total_line):
                lines.setdefault(total_line, {})["under"] = Decimal(value["odd"])
    return _select_balanced_line(lines, "over", "under")


def map_odds_snapshots(payload: dict) -> list[ExternalOddsSnapshot]:
    snapshots = []
    captured_at = now_beijing()
    for item in payload.get("response", []):
        source_match_id = str(item["fixture"]["id"])
        for bookmaker in item.get("bookmakers", []):
            asian_handicap, home_odds, away_odds = _extract_asian_handicap(bookmaker)
            total_line, over_odds, under_odds = _extract_total_line(bookmaker)
            if asian_handicap is None and total_line is None:
                continue
            snapshots.append(
                ExternalOddsSnapshot(
                    source_name=SOURCE_NAME,
                    source_match_id=source_match_id,
                    captured_at=captured_at,
                    bookmaker=bookmaker["name"],
                    asian_handicap=asian_handicap,
                    home_odds=home_odds,
                    away_odds=away_odds,
                    total_line=total_line,
                    over_odds=over_odds,
                    under_odds=under_odds,
                )
            )
    return snapshots

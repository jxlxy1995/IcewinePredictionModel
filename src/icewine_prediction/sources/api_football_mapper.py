from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

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


def _extract_asian_handicap(bookmaker: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    bet = _find_bet(bookmaker, "Asian Handicap")
    if bet is None:
        return None, None, None
    handicap = None
    home_odds = None
    away_odds = None
    for value in bet.get("values", []):
        label = value["value"]
        if label.startswith("Home "):
            handicap = _parse_prefixed_decimal(label, "Home ")
            home_odds = Decimal(value["odd"])
        elif label.startswith("Away "):
            away_odds = Decimal(value["odd"])
    return handicap, home_odds, away_odds


def _extract_total_line(bookmaker: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    bet = _find_bet(bookmaker, "Goals Over/Under")
    if bet is None:
        return None, None, None
    total_line = None
    over_odds = None
    under_odds = None
    for value in bet.get("values", []):
        label = value["value"]
        if label.startswith("Over "):
            total_line = _parse_prefixed_decimal(label, "Over ")
            over_odds = Decimal(value["odd"])
        elif label.startswith("Under "):
            under_odds = Decimal(value["odd"])
    return total_line, over_odds, under_odds


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

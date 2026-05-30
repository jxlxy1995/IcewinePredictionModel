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
    season: int | None
    home_source_team_id: str
    home_team_name: str
    away_source_team_id: str
    away_team_name: str
    kickoff_time: datetime
    status: str
    home_score: int | None
    away_score: int | None
    league_logo_url: str | None = None
    league_flag_url: str | None = None
    standings_supported: bool | None = None
    league_round: str | None = None
    home_team_logo_url: str | None = None
    home_winner: bool | None = None
    away_team_logo_url: str | None = None
    away_winner: bool | None = None
    referee: str | None = None
    fixture_timezone: str | None = None
    fixture_timestamp: int | None = None
    first_period_started_at: int | None = None
    second_period_started_at: int | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    status_long: str | None = None
    status_short: str | None = None
    elapsed: int | None = None
    extra: int | None = None
    halftime_home_score: int | None = None
    halftime_away_score: int | None = None
    fulltime_home_score: int | None = None
    fulltime_away_score: int | None = None
    extratime_home_score: int | None = None
    extratime_away_score: int | None = None
    penalty_home_score: int | None = None
    penalty_away_score: int | None = None


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
    match_winner_home_odds: Decimal | None = None
    match_winner_draw_odds: Decimal | None = None
    match_winner_away_odds: Decimal | None = None


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
        score = item.get("score") or {}
        status = fixture.get("status") or {}
        periods = fixture.get("periods") or {}
        venue = fixture.get("venue") or {}
        halftime = score.get("halftime") or {}
        fulltime = score.get("fulltime") or {}
        extratime = score.get("extratime") or {}
        penalty = score.get("penalty") or {}
        home_team = teams["home"]
        away_team = teams["away"]
        fixtures.append(
            ExternalFixture(
                source_name=SOURCE_NAME,
                source_match_id=str(fixture["id"]),
                source_league_id=str(league["id"]),
                league_name=league["name"],
                country=league["country"],
                season=league.get("season"),
                league_logo_url=league.get("logo"),
                league_flag_url=league.get("flag"),
                standings_supported=league.get("standings"),
                league_round=league.get("round"),
                home_source_team_id=str(home_team["id"]),
                home_team_name=home_team["name"],
                home_team_logo_url=home_team.get("logo"),
                home_winner=home_team.get("winner"),
                away_source_team_id=str(away_team["id"]),
                away_team_name=away_team["name"],
                away_team_logo_url=away_team.get("logo"),
                away_winner=away_team.get("winner"),
                kickoff_time=datetime.fromisoformat(fixture["date"]),
                referee=fixture.get("referee"),
                fixture_timezone=fixture.get("timezone"),
                fixture_timestamp=fixture.get("timestamp"),
                first_period_started_at=periods.get("first"),
                second_period_started_at=periods.get("second"),
                venue_id=venue.get("id"),
                venue_name=venue.get("name"),
                venue_city=venue.get("city"),
                status=_map_status(status["short"]),
                status_long=status.get("long"),
                status_short=status.get("short"),
                elapsed=status.get("elapsed"),
                extra=status.get("extra"),
                home_score=_main_score(goals, fulltime, "home"),
                away_score=_main_score(goals, fulltime, "away"),
                halftime_home_score=halftime.get("home"),
                halftime_away_score=halftime.get("away"),
                fulltime_home_score=fulltime.get("home"),
                fulltime_away_score=fulltime.get("away"),
                extratime_home_score=extratime.get("home"),
                extratime_away_score=extratime.get("away"),
                penalty_home_score=penalty.get("home"),
                penalty_away_score=penalty.get("away"),
            )
        )
    return fixtures


def _main_score(goals: dict, fulltime: dict, side: str) -> int | None:
    if fulltime.get(side) is not None:
        return fulltime.get(side)
    return goals.get(side)


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


def _extract_match_winner(bookmaker: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    bet = _find_bet(bookmaker, "Match Winner")
    if bet is None:
        return None, None, None
    odds_by_side: dict[str, Decimal] = {}
    for value in bet.get("values", []):
        label = value["value"]
        if label == "Home":
            odds_by_side["home"] = Decimal(value["odd"])
        elif label == "Draw":
            odds_by_side["draw"] = Decimal(value["odd"])
        elif label == "Away":
            odds_by_side["away"] = Decimal(value["odd"])
    return odds_by_side.get("home"), odds_by_side.get("draw"), odds_by_side.get("away")


def map_odds_snapshots(payload: dict) -> list[ExternalOddsSnapshot]:
    snapshots = []
    captured_at = now_beijing()
    for item in payload.get("response", []):
        source_match_id = str(item["fixture"]["id"])
        for bookmaker in item.get("bookmakers", []):
            asian_handicap, home_odds, away_odds = _extract_asian_handicap(bookmaker)
            total_line, over_odds, under_odds = _extract_total_line(bookmaker)
            (
                match_winner_home_odds,
                match_winner_draw_odds,
                match_winner_away_odds,
            ) = _extract_match_winner(bookmaker)
            if (
                asian_handicap is None
                and total_line is None
                and match_winner_home_odds is None
                and match_winner_draw_odds is None
                and match_winner_away_odds is None
            ):
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
                    match_winner_home_odds=match_winner_home_odds,
                    match_winner_draw_odds=match_winner_draw_odds,
                    match_winner_away_odds=match_winner_away_odds,
                )
            )
    return snapshots

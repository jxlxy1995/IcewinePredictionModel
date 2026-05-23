from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re
import unicodedata
from zoneinfo import ZoneInfo

from icewine_prediction.models import Match

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC_TIMEZONE = ZoneInfo("UTC")


@dataclass(frozen=True)
class OddsPapiFixture:
    fixture_id: str
    tournament_id: int
    start_time: datetime
    home_team_name: str
    away_team_name: str


@dataclass(frozen=True)
class OddsSourceMatchCandidate:
    fixture: OddsPapiFixture
    confidence: Decimal
    reason: str


COMMON_TEAM_PREFIXES = {
    "afc",
    "as",
    "ca",
    "cd",
    "cf",
    "fc",
    "rcd",
    "sc",
    "ssc",
    "sv",
    "ud",
    "us",
}

COMMON_TEAM_SUFFIXES = {
    "afc",
    "calcio",
    "cf",
    "club",
    "fc",
    "football",
    "fk",
    "sc",
    "sv",
}

SOFT_TEAM_PREFIXES = {
    "real",
}


def normalize_team_name(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_name)
    tokens = [token for token in cleaned.split() if token]
    while tokens and tokens[0] in COMMON_TEAM_PREFIXES:
        tokens = tokens[1:]
    while tokens and tokens[-1] in COMMON_TEAM_SUFFIXES:
        tokens = tokens[:-1]
    return " ".join(tokens)


def find_best_odds_source_match(
    match: Match,
    fixtures: list[OddsPapiFixture],
    api_football_to_oddspapi_tournament_ids: dict[str, int],
    max_time_delta_seconds: int = 7200,
) -> OddsSourceMatchCandidate | None:
    expected_tournament_id = api_football_to_oddspapi_tournament_ids.get(
        str(match.league.source_league_id)
    )
    if expected_tournament_id is None:
        return None

    candidates = []
    for fixture in fixtures:
        if fixture.tournament_id != expected_tournament_id:
            continue
        time_delta = abs(
            (
                _as_utc(match.kickoff_time, default_timezone=BEIJING_TIMEZONE)
                - _as_utc(fixture.start_time, default_timezone=UTC_TIMEZONE)
            ).total_seconds()
        )
        if time_delta > max_time_delta_seconds:
            continue
        home_score = _team_name_similarity(match.home_team.canonical_name, fixture.home_team_name)
        away_score = _team_name_similarity(match.away_team.canonical_name, fixture.away_team_name)
        if home_score == Decimal("0") or away_score == Decimal("0"):
            continue
        confidence = min(home_score, away_score)
        candidates.append(
            OddsSourceMatchCandidate(
                fixture=fixture,
                confidence=confidence,
                reason=f"league/time/team match; time_delta_seconds={int(time_delta)}",
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.confidence)


def _as_utc(value: datetime, default_timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_timezone)
    return value.astimezone(UTC_TIMEZONE)


def _team_name_similarity(left: str, right: str) -> Decimal:
    normalized_left = normalize_team_name(left)
    normalized_right = normalize_team_name(right)
    if normalized_left == normalized_right:
        return Decimal("1.0000")
    if _matches_with_soft_prefix(normalized_left, normalized_right):
        return Decimal("1.0000")
    if normalized_left and normalized_right and (
        normalized_left in normalized_right or normalized_right in normalized_left
    ):
        return Decimal("0.9000")
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    if not left_tokens or not right_tokens:
        return Decimal("0")
    overlap = left_tokens & right_tokens
    if not overlap:
        return Decimal("0")
    return Decimal(len(overlap)) / Decimal(max(len(left_tokens), len(right_tokens)))


def _matches_with_soft_prefix(left: str, right: str) -> bool:
    left_tokens = left.split()
    right_tokens = right.split()
    if len(left_tokens) > len(right_tokens):
        left_tokens, right_tokens = right_tokens, left_tokens
    if not left_tokens or len(right_tokens) <= len(left_tokens):
        return False
    prefix_tokens = right_tokens[: len(right_tokens) - len(left_tokens)]
    suffix_tokens = right_tokens[-len(left_tokens) :]
    return suffix_tokens == left_tokens and all(
        token in SOFT_TEAM_PREFIXES for token in prefix_tokens
    )

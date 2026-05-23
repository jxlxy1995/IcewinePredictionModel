from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from icewine_prediction.models import League, Match


@dataclass(frozen=True)
class LeagueCoverageSummary:
    league_name: str
    country_or_region: str
    total_matches: int
    finished_matches: int
    scored_matches: int
    matches_with_odds: int
    matches_with_asian_handicap: int
    matches_with_total_goals: int
    odds_coverage_ratio: Decimal
    asian_handicap_coverage_ratio: Decimal
    total_goals_coverage_ratio: Decimal


def _coverage_ratio(count: int, total: int) -> Decimal:
    if total == 0:
        return Decimal("0.0000")
    return (Decimal(count) / Decimal(total)).quantize(
        Decimal("0.0000"),
        rounding=ROUND_HALF_UP,
    )


def _summarize_league(league: League, matches: list[Match]) -> LeagueCoverageSummary:
    total_matches = len(matches)
    finished_matches = len([match for match in matches if match.status == "finished"])
    scored_matches = len(
        [
            match
            for match in matches
            if match.home_score is not None and match.away_score is not None
        ]
    )
    matches_with_odds = 0
    matches_with_asian_handicap = 0
    matches_with_total_goals = 0
    for match in matches:
        if not match.odds_snapshots:
            continue
        matches_with_odds += 1
        if any(snapshot.asian_handicap is not None for snapshot in match.odds_snapshots):
            matches_with_asian_handicap += 1
        if any(snapshot.total_line is not None for snapshot in match.odds_snapshots):
            matches_with_total_goals += 1
    return LeagueCoverageSummary(
        league_name=league.name,
        country_or_region=league.country_or_region,
        total_matches=total_matches,
        finished_matches=finished_matches,
        scored_matches=scored_matches,
        matches_with_odds=matches_with_odds,
        matches_with_asian_handicap=matches_with_asian_handicap,
        matches_with_total_goals=matches_with_total_goals,
        odds_coverage_ratio=_coverage_ratio(matches_with_odds, total_matches),
        asian_handicap_coverage_ratio=_coverage_ratio(
            matches_with_asian_handicap,
            total_matches,
        ),
        total_goals_coverage_ratio=_coverage_ratio(
            matches_with_total_goals,
            total_matches,
        ),
    )


def build_history_coverage_report(
    session: Session,
    season: int | None = None,
) -> list[LeagueCoverageSummary]:
    leagues = session.query(League).order_by(League.priority.desc(), League.name.asc()).all()
    summaries = []
    for league in leagues:
        matches = list(league.matches)
        if season is not None:
            matches = [match for match in matches if match.season == season]
        if not matches:
            continue
        summaries.append(_summarize_league(league, matches))
    return summaries

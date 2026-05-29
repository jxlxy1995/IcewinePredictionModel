from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


RATIO_QUANT = Decimal("0.0000")
DAYS_QUANT = Decimal("0.00")
DEFAULT_VALIDATION_RATIO = Decimal("0.2000")

FEATURE_FIELDNAMES = (
    "match_id",
    "source_match_id",
    "league_name",
    "league_source_id",
    "season",
    "kickoff_time",
    "split",
    "home_team_name",
    "away_team_name",
    "target_match_result",
    "target_home_score",
    "target_away_score",
    "target_total_goals",
    "target_asian_handicap_home_result",
    "target_asian_handicap_away_result",
    "asian_handicap_close_line",
    "asian_handicap_home_odds",
    "asian_handicap_away_odds",
    "total_goals_close_line",
    "target_total_goals_over_result",
    "target_total_goals_under_result",
    "total_goals_over_odds",
    "total_goals_under_odds",
    "home_prior_matches",
    "home_prior_points_per_match",
    "home_prior_win_rate",
    "home_prior_draw_rate",
    "home_prior_loss_rate",
    "home_prior_goals_for_per_match",
    "home_prior_goals_against_per_match",
    "home_prior_home_matches",
    "home_prior_home_points_per_match",
    "home_rest_days",
    "away_prior_matches",
    "away_prior_points_per_match",
    "away_prior_win_rate",
    "away_prior_draw_rate",
    "away_prior_loss_rate",
    "away_prior_goals_for_per_match",
    "away_prior_goals_against_per_match",
    "away_prior_away_matches",
    "away_prior_away_points_per_match",
    "away_rest_days",
    "match_winner_home_implied_probability",
    "match_winner_draw_implied_probability",
    "match_winner_away_implied_probability",
    "match_winner_overround",
    "asian_handicap_home_implied_probability",
    "asian_handicap_away_implied_probability",
    "asian_handicap_overround",
    "total_goals_over_implied_probability",
    "total_goals_under_implied_probability",
    "total_goals_overround",
    "quality_tags",
)


@dataclass(frozen=True)
class BaselineFeatureSetReport:
    csv_path: Path
    row_count: int
    train_rows: int
    validation_rows: int
    validation_ratio: Decimal
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    by_league: dict[str, dict[str, int]]
    zero_history_rows: int


@dataclass(frozen=True)
class BaselineFeatureSet:
    rows: list[dict[str, str]]
    report: BaselineFeatureSetReport


@dataclass
class _TeamState:
    matches: int = 0
    points: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    home_matches: int = 0
    home_points: int = 0
    away_matches: int = 0
    away_points: int = 0
    last_kickoff: datetime | None = None


def build_baseline_feature_set(
    csv_path: Path,
    *,
    validation_ratio: Decimal | float | str = DEFAULT_VALIDATION_RATIO,
) -> BaselineFeatureSet:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    sorted_rows = sorted(rows, key=lambda row: (_parse_datetime(row["kickoff_time"]), int(row["match_id"])))
    split_by_match_id = _build_time_split(sorted_rows, _as_decimal(validation_ratio))
    team_states: dict[tuple[str, str], _TeamState] = {}
    feature_rows: list[dict[str, str]] = []

    for row in sorted_rows:
        league_name = row["league_name"]
        home_team = row["home_team_name"]
        away_team = row["away_team_name"]
        kickoff = _parse_datetime(row["kickoff_time"])
        home_state = team_states.setdefault((league_name, home_team), _TeamState())
        away_state = team_states.setdefault((league_name, away_team), _TeamState())
        feature_rows.append(
            _build_feature_row(
                row,
                split=split_by_match_id[row["match_id"]],
                kickoff=kickoff,
                home_state=home_state,
                away_state=away_state,
            )
        )
        _update_team_states(row, kickoff, home_state, away_state)

    return BaselineFeatureSet(
        rows=feature_rows,
        report=_build_report(csv_path, feature_rows, _as_decimal(validation_ratio)),
    )


def write_baseline_feature_set_csv(feature_set: BaselineFeatureSet, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FEATURE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(feature_set.rows)


def format_baseline_feature_set_report(report: BaselineFeatureSetReport) -> str:
    lines = [
        "# Baseline Feature Set v1",
        "",
        f"- Source CSV: `{report.csv_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Rows | {report.row_count} |",
        f"| Train rows | {report.train_rows} |",
        f"| Validation rows | {report.validation_rows} |",
        f"| Validation ratio | {report.validation_ratio} |",
        f"| Train start | {report.train_start} |",
        f"| Train end | {report.train_end} |",
        f"| Validation start | {report.validation_start} |",
        f"| Validation end | {report.validation_end} |",
        f"| Zero-history rows | {report.zero_history_rows} |",
        "",
        "## Time Split",
        "",
        "| Split | Start | End |",
        "| --- | --- | --- |",
        f"| Train | {report.train_start} | {report.train_end} |",
        f"| Validation | {report.validation_start} | {report.validation_end} |",
        "",
        "## League Split",
        "",
        "| League | Rows | Train | Validation |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {league_name} | {counts['rows']} | {counts['train']} | {counts['validation']} |"
        for league_name, counts in sorted(
            report.by_league.items(),
            key=lambda item: (-item[1]["rows"], item[0]),
        )
    )
    return "\n".join(lines)


def write_baseline_feature_set_report(
    report: BaselineFeatureSetReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_baseline_feature_set_report(report) + "\n", encoding="utf-8")


def _build_feature_row(
    row: dict[str, str],
    *,
    split: str,
    kickoff: datetime,
    home_state: _TeamState,
    away_state: _TeamState,
) -> dict[str, str]:
    return {
        "match_id": row["match_id"],
        "source_match_id": row.get("source_match_id", ""),
        "league_name": row["league_name"],
        "league_source_id": row.get("league_source_id", ""),
        "season": row.get("season", ""),
        "kickoff_time": row["kickoff_time"],
        "split": split,
        "home_team_name": row["home_team_name"],
        "away_team_name": row["away_team_name"],
        "target_match_result": row["match_result"],
        "target_home_score": row["home_score"],
        "target_away_score": row["away_score"],
        "target_total_goals": row["total_goals"],
        "target_asian_handicap_home_result": row.get("asian_handicap_home_result", ""),
        "target_asian_handicap_away_result": row.get("asian_handicap_away_result", ""),
        "asian_handicap_close_line": row.get("asian_handicap_close_line", ""),
        "asian_handicap_home_odds": row.get("asian_handicap_home_odds", ""),
        "asian_handicap_away_odds": row.get("asian_handicap_away_odds", ""),
        "total_goals_close_line": row.get("total_goals_close_line", ""),
        "target_total_goals_over_result": row.get("total_goals_over_result", ""),
        "target_total_goals_under_result": row.get("total_goals_under_result", ""),
        "total_goals_over_odds": row.get("total_goals_over_odds", ""),
        "total_goals_under_odds": row.get("total_goals_under_odds", ""),
        **_team_features("home", home_state, kickoff, venue="home"),
        **_team_features("away", away_state, kickoff, venue="away"),
        "match_winner_home_implied_probability": row.get(
            "match_winner_home_implied_probability", ""
        ),
        "match_winner_draw_implied_probability": row.get(
            "match_winner_draw_implied_probability", ""
        ),
        "match_winner_away_implied_probability": row.get(
            "match_winner_away_implied_probability", ""
        ),
        "match_winner_overround": row.get("match_winner_overround", ""),
        "asian_handicap_home_implied_probability": row.get(
            "asian_handicap_home_implied_probability", ""
        ),
        "asian_handicap_away_implied_probability": row.get(
            "asian_handicap_away_implied_probability", ""
        ),
        "asian_handicap_overround": row.get("asian_handicap_overround", ""),
        "total_goals_over_implied_probability": row.get(
            "total_goals_over_implied_probability", ""
        ),
        "total_goals_under_implied_probability": row.get(
            "total_goals_under_implied_probability", ""
        ),
        "total_goals_overround": row.get("total_goals_overround", ""),
        "quality_tags": row.get("quality_tags", ""),
    }


def _team_features(
    prefix: str,
    state: _TeamState,
    kickoff: datetime,
    *,
    venue: str,
) -> dict[str, str]:
    venue_matches = state.home_matches if venue == "home" else state.away_matches
    venue_points = state.home_points if venue == "home" else state.away_points
    return {
        f"{prefix}_prior_matches": str(state.matches),
        f"{prefix}_prior_points_per_match": _ratio(state.points, state.matches),
        f"{prefix}_prior_win_rate": _ratio(state.wins, state.matches),
        f"{prefix}_prior_draw_rate": _ratio(state.draws, state.matches),
        f"{prefix}_prior_loss_rate": _ratio(state.losses, state.matches),
        f"{prefix}_prior_goals_for_per_match": _ratio(state.goals_for, state.matches),
        f"{prefix}_prior_goals_against_per_match": _ratio(state.goals_against, state.matches),
        f"{prefix}_prior_{venue}_matches": str(venue_matches),
        f"{prefix}_prior_{venue}_points_per_match": _ratio(venue_points, venue_matches),
        f"{prefix}_rest_days": _rest_days(state.last_kickoff, kickoff),
    }


def _update_team_states(
    row: dict[str, str],
    kickoff: datetime,
    home_state: _TeamState,
    away_state: _TeamState,
) -> None:
    home_score = int(row["home_score"])
    away_score = int(row["away_score"])
    if home_score > away_score:
        home_points, away_points = 3, 0
        home_result, away_result = "win", "loss"
    elif home_score < away_score:
        home_points, away_points = 0, 3
        home_result, away_result = "loss", "win"
    else:
        home_points, away_points = 1, 1
        home_result, away_result = "draw", "draw"
    _apply_team_result(
        home_state,
        points=home_points,
        result=home_result,
        goals_for=home_score,
        goals_against=away_score,
        is_home=True,
        kickoff=kickoff,
    )
    _apply_team_result(
        away_state,
        points=away_points,
        result=away_result,
        goals_for=away_score,
        goals_against=home_score,
        is_home=False,
        kickoff=kickoff,
    )


def _apply_team_result(
    state: _TeamState,
    *,
    points: int,
    result: str,
    goals_for: int,
    goals_against: int,
    is_home: bool,
    kickoff: datetime,
) -> None:
    state.matches += 1
    state.points += points
    state.goals_for += goals_for
    state.goals_against += goals_against
    state.wins += 1 if result == "win" else 0
    state.draws += 1 if result == "draw" else 0
    state.losses += 1 if result == "loss" else 0
    if is_home:
        state.home_matches += 1
        state.home_points += points
    else:
        state.away_matches += 1
        state.away_points += points
    state.last_kickoff = kickoff


def _build_time_split(rows: list[dict[str, str]], validation_ratio: Decimal) -> dict[str, str]:
    if not rows:
        return {}
    validation_count = int((Decimal(len(rows)) * validation_ratio).to_integral_value(rounding=ROUND_HALF_UP))
    if validation_ratio > 0:
        validation_count = max(1, validation_count)
    validation_count = min(len(rows), validation_count)
    validation_start_kickoff = _parse_datetime(rows[-validation_count]["kickoff_time"])
    return {
        row["match_id"]: (
            "validation"
            if _parse_datetime(row["kickoff_time"]) >= validation_start_kickoff
            else "train"
        )
        for row in rows
    }


def _build_report(
    csv_path: Path,
    rows: list[dict[str, str]],
    validation_ratio: Decimal,
) -> BaselineFeatureSetReport:
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    return BaselineFeatureSetReport(
        csv_path=csv_path,
        row_count=len(rows),
        train_rows=len(train_rows),
        validation_rows=len(validation_rows),
        validation_ratio=validation_ratio.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP),
        train_start=_first_time(train_rows),
        train_end=_last_time(train_rows),
        validation_start=_first_time(validation_rows),
        validation_end=_last_time(validation_rows),
        by_league=_count_by_league(rows),
        zero_history_rows=sum(
            1
            for row in rows
            if row["home_prior_matches"] == "0" or row["away_prior_matches"] == "0"
        ),
    )


def _count_by_league(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        league_counts = counts.setdefault(row["league_name"], {"rows": 0, "train": 0, "validation": 0})
        league_counts["rows"] += 1
        league_counts[row["split"]] += 1
    return counts


def _first_time(rows: list[dict[str, str]]) -> str:
    return rows[0]["kickoff_time"] if rows else ""


def _last_time(rows: list[dict[str, str]]) -> str:
    return rows[-1]["kickoff_time"] if rows else ""


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return str(RATIO_QUANT)
    return str((Decimal(numerator) / Decimal(denominator)).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP))


def _rest_days(previous: datetime | None, kickoff: datetime) -> str:
    if previous is None:
        return ""
    days = Decimal(str((kickoff - previous).total_seconds() / 86400))
    return str(days.quantize(DAYS_QUANT, rounding=ROUND_HALF_UP))


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _as_decimal(value: Decimal | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))

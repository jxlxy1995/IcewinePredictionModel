from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_home_cover_signal_research_service import (
    HomeCoverFoldCandidateSet,
    build_home_cover_signal_research_report_from_fold_candidates,
    format_baseline_home_cover_signal_research_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate


def test_home_cover_signal_research_rates_promotable_watchlist_and_rejected():
    report = build_home_cover_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(
                1,
                _candidates("home_favorite", 8, Decimal("0.1000"), wins=6)
                + _candidates("pickem", 8, Decimal("0.1000"), wins=6)
                + _candidates("home_underdog", 8, Decimal("0.1000"), wins=2),
            ),
            _fold(
                2,
                _candidates("home_favorite", 8, Decimal("0.1000"), wins=6)
                + _candidates("pickem", 8, Decimal("0.1000"), wins=6)
                + _candidates("home_underdog", 8, Decimal("0.1000"), wins=2),
            ),
            _fold(
                3,
                _candidates("home_favorite", 8, Decimal("0.1000"), wins=5)
                + _candidates("pickem", 8, Decimal("0.1000"), wins=3)
                + _candidates("home_underdog", 8, Decimal("0.1000"), wins=2),
            ),
            _fold(
                4,
                _candidates("home_favorite", 8, Decimal("0.1000"), wins=5)
                + _candidates("pickem", 8, Decimal("0.1000"), wins=3)
                + _candidates("home_underdog", 8, Decimal("0.1000"), wins=2),
            ),
            _fold(
                5,
                _candidates("home_favorite", 8, Decimal("0.1000"), wins=4)
                + _candidates("pickem", 8, Decimal("0.1000"), wins=3)
                + _candidates("home_underdog", 8, Decimal("0.1000"), wins=2),
            ),
        ],
        thresholds=("0.10",),
    )

    ratings = {summary.line_bucket: summary.rating for summary in report.candidate_summaries}

    assert ratings["home_favorite"] == "promotable"
    assert ratings["pickem"] == "watchlist"
    assert ratings["home_underdog"] == "rejected"


def test_format_home_cover_signal_research_report_includes_core_tables():
    report = build_home_cover_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(1, _candidates("home_favorite", 8, Decimal("0.1000"), wins=6)),
            _fold(2, _candidates("home_favorite", 8, Decimal("0.1000"), wins=6)),
            _fold(3, _candidates("home_favorite", 8, Decimal("0.1000"), wins=5)),
            _fold(4, _candidates("home_favorite", 8, Decimal("0.1000"), wins=5)),
            _fold(5, _candidates("home_favorite", 8, Decimal("0.1000"), wins=4)),
        ],
        thresholds=("0.10",),
    )

    text = format_baseline_home_cover_signal_research_report(report)

    assert "# Baseline Home Cover Signal Research" in text
    assert "| Rating | Candidates |" in text
    assert "| Line bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI |" in text
    assert "## Promotion Recommendation" in text


def _fold(index: int, candidates: list[SandboxCandidate]) -> HomeCoverFoldCandidateSet:
    return HomeCoverFoldCandidateSet(
        fold_index=index,
        train_rows=20,
        validation_rows=20,
        candidates=candidates,
    )


def _candidates(
    bucket: str,
    count: int,
    edge: Decimal,
    *,
    wins: int,
) -> list[SandboxCandidate]:
    line_by_bucket = {
        "home_favorite": Decimal("-0.50"),
        "pickem": Decimal("0.00"),
        "home_underdog": Decimal("0.50"),
    }
    candidates = []
    for index in range(count):
        won = index < wins
        candidates.append(
            SandboxCandidate(
                match_id=f"{bucket}-{index}",
                kickoff_time=f"2026-01-{index + 1:02d}T12:00:00+08:00",
                league_name="League",
                home_team_name="Home",
                away_team_name="Away",
                market_type="asian_handicap",
                line=line_by_bucket[bucket],
                side="home_cover",
                odds=Decimal("2.0000"),
                model_probability=Decimal("0.6000"),
                market_probability=Decimal("0.5000"),
                edge=edge,
                actual_side="home_cover" if won else "away_cover",
                profit=Decimal("1.0000") if won else Decimal("-1.0000"),
            )
        )
    return candidates

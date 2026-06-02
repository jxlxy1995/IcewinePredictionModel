from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.baseline_total_goals_v3_signal_research_service import (
    TotalGoalsV3FoldCandidateSet,
    build_total_goals_v3_signal_research_report_from_fold_candidates,
    format_baseline_total_goals_v3_signal_research_report,
)


def test_total_goals_v3_signal_research_rates_promotable_candidates():
    report = build_total_goals_v3_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(1, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=6)),
            _fold(2, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=6)),
            _fold(3, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=5)),
            _fold(4, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=5)),
            _fold(5, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=4)),
        ],
        thresholds=("0.08",),
    )

    candidate = report.candidate_summaries[0]

    assert candidate.rating == "promotable"
    assert candidate.side_bucket == "over@mid_2.75"
    assert candidate.candidate_count == 40
    assert candidate.positive_roi_folds == 4
    assert candidate.roi is not None and candidate.roi >= Decimal("0.0500")
    assert candidate.overlap_count == 40
    assert candidate.incremental_count == 0


def test_total_goals_v3_signal_research_rates_watchlist_and_rejected_candidates():
    report = build_total_goals_v3_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(
                1,
                _candidates("under", Decimal("2.50"), 8, Decimal("0.0800"), wins=6)
                + _candidates("over", Decimal("3.00"), 8, Decimal("0.0800"), wins=2),
            ),
            _fold(
                2,
                _candidates("under", Decimal("2.50"), 8, Decimal("0.0800"), wins=6)
                + _candidates("over", Decimal("3.00"), 8, Decimal("0.0800"), wins=2),
            ),
            _fold(
                3,
                _candidates("under", Decimal("2.50"), 8, Decimal("0.0800"), wins=3)
                + _candidates("over", Decimal("3.00"), 8, Decimal("0.0800"), wins=2),
            ),
            _fold(
                4,
                _candidates("under", Decimal("2.50"), 8, Decimal("0.0800"), wins=3)
                + _candidates("over", Decimal("3.00"), 8, Decimal("0.0800"), wins=2),
            ),
            _fold(
                5,
                _candidates("under", Decimal("2.50"), 8, Decimal("0.0800"), wins=3)
                + _candidates("over", Decimal("3.00"), 8, Decimal("0.0800"), wins=2),
            ),
        ],
        thresholds=("0.08",),
    )

    ratings = {summary.side_bucket: summary.rating for summary in report.candidate_summaries}

    assert ratings["under@mid_2.50"] == "watchlist"
    assert ratings["over@high_>=3.00"] == "rejected"


def test_total_goals_v3_signal_research_reports_incremental_overlap_metrics():
    report = build_total_goals_v3_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(1, _candidates("under", Decimal("2.75"), 6, Decimal("0.0600"), wins=5)),
            _fold(2, _candidates("under", Decimal("2.75"), 6, Decimal("0.0600"), wins=5)),
            _fold(3, _candidates("under", Decimal("2.75"), 6, Decimal("0.0600"), wins=5)),
            _fold(4, _candidates("under", Decimal("2.75"), 6, Decimal("0.0600"), wins=5)),
            _fold(5, _candidates("under", Decimal("2.75"), 6, Decimal("0.0600"), wins=5)),
        ],
        thresholds=("0.06",),
    )

    candidate = report.candidate_summaries[0]

    assert candidate.candidate_count == 30
    assert candidate.overlap_count == 10
    assert candidate.overlap_share == Decimal("0.3333")
    assert candidate.incremental_count == 20
    assert candidate.incremental_roi is not None


def test_format_total_goals_v3_signal_research_report_includes_gate_and_recommendations():
    report = build_total_goals_v3_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(1, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=6)),
            _fold(2, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=6)),
            _fold(3, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=5)),
            _fold(4, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=5)),
            _fold(5, _candidates("over", Decimal("2.75"), 8, Decimal("0.0800"), wins=4)),
        ],
        thresholds=("0.08",),
    )

    text = format_baseline_total_goals_v3_signal_research_report(report)

    assert "# Baseline Total Goals v3 Signal Research" in text
    assert "| Rating | Candidates |" in text
    assert "| Side bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI |" in text
    assert "## Promotion Recommendation" in text


def _fold(index: int, candidates: list[SandboxCandidate]) -> TotalGoalsV3FoldCandidateSet:
    return TotalGoalsV3FoldCandidateSet(
        fold_index=index,
        train_rows=20,
        validation_rows=20,
        candidates=candidates,
    )


def _candidates(
    side: str,
    line: Decimal,
    count: int,
    edge: Decimal,
    *,
    wins: int,
) -> list[SandboxCandidate]:
    candidates = []
    for index in range(count):
        won = index < wins
        candidates.append(
            SandboxCandidate(
                match_id=f"{side}-{line}-{edge}-{index}",
                kickoff_time=f"2026-01-{index + 1:02d}T12:00:00+08:00",
                league_name="League",
                home_team_name="Home",
                away_team_name="Away",
                market_type="total_goals",
                line=line,
                side=side,
                odds=Decimal("2.0000"),
                model_probability=Decimal("0.6000"),
                market_probability=Decimal("0.5000"),
                edge=edge if index % 3 != 0 else edge + Decimal("0.0200"),
                actual_side=side if won else ("under" if side == "over" else "over"),
                profit=Decimal("1.0000") if won else Decimal("-1.0000"),
            )
        )
    return candidates

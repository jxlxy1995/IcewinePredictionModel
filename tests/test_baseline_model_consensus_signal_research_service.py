from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_model_consensus_signal_research_service import (
    ModelConsensusCandidate,
    ModelConsensusFoldCandidateSet,
    build_model_consensus_signal_research_report_from_fold_candidates,
    format_baseline_model_consensus_signal_research_report,
)


def test_model_consensus_signal_research_rates_confirmed_and_diverged_buckets():
    report = build_model_consensus_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(
                1,
                _candidates("asian_handicap", "home_cover", Decimal("-0.50"), 8, Decimal("0.1000"), wins=6)
                + _candidates(
                    "asian_handicap",
                    "away_cover",
                    Decimal("-0.50"),
                    8,
                    Decimal("0.1000"),
                    wins=2,
                    calibrated_side="home_cover",
                    calibrated_edge=Decimal("0.0300"),
                ),
            ),
            _fold(
                2,
                _candidates("asian_handicap", "home_cover", Decimal("-0.50"), 8, Decimal("0.1000"), wins=6)
                + _candidates(
                    "asian_handicap",
                    "away_cover",
                    Decimal("-0.50"),
                    8,
                    Decimal("0.1000"),
                    wins=2,
                    calibrated_side="home_cover",
                    calibrated_edge=Decimal("0.0300"),
                ),
            ),
            _fold(
                3,
                _candidates("asian_handicap", "home_cover", Decimal("-0.50"), 8, Decimal("0.1000"), wins=5)
                + _candidates(
                    "asian_handicap",
                    "away_cover",
                    Decimal("-0.50"),
                    8,
                    Decimal("0.1000"),
                    wins=2,
                    calibrated_side="home_cover",
                    calibrated_edge=Decimal("0.0300"),
                ),
            ),
            _fold(
                4,
                _candidates("asian_handicap", "home_cover", Decimal("-0.50"), 8, Decimal("0.1000"), wins=5)
                + _candidates(
                    "asian_handicap",
                    "away_cover",
                    Decimal("-0.50"),
                    8,
                    Decimal("0.1000"),
                    wins=2,
                    calibrated_side="home_cover",
                    calibrated_edge=Decimal("0.0300"),
                ),
            ),
            _fold(
                5,
                _candidates("asian_handicap", "home_cover", Decimal("-0.50"), 8, Decimal("0.1000"), wins=4)
                + _candidates(
                    "asian_handicap",
                    "away_cover",
                    Decimal("-0.50"),
                    8,
                    Decimal("0.1000"),
                    wins=2,
                    calibrated_side="home_cover",
                    calibrated_edge=Decimal("0.0300"),
                ),
            ),
        ],
        thresholds=("0.10",),
        confirmation_threshold="0.00",
    )

    ratings = {summary.signal_bucket: summary.rating for summary in report.candidate_summaries}

    assert ratings["asian_handicap:confirmed:home_cover@home_favorite"] == "promotable"
    assert ratings["asian_handicap:diverged:away_cover@home_favorite"] == "rejected"


def test_model_consensus_signal_research_treats_weak_same_side_as_diverged():
    report = build_model_consensus_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=20,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(
                1,
                _candidates(
                    "total_goals",
                    "under",
                    Decimal("2.25"),
                    5,
                    Decimal("0.1000"),
                    wins=3,
                    calibrated_side="under",
                    calibrated_edge=Decimal("-0.0100"),
                ),
            )
        ],
        thresholds=("0.10",),
        confirmation_threshold="0.00",
    )

    assert report.candidate_summaries[0].signal_bucket == "total_goals:diverged:under@low_<=2.25"


def test_format_model_consensus_signal_research_report_includes_core_tables():
    report = build_model_consensus_signal_research_report_from_fold_candidates(
        Path("features.csv"),
        row_count=100,
        train_ratio=Decimal("0.6000"),
        validation_ratio=Decimal("0.1000"),
        fold_candidates=[
            _fold(1, _candidates("total_goals", "over", Decimal("2.75"), 8, Decimal("0.1000"), wins=6)),
            _fold(2, _candidates("total_goals", "over", Decimal("2.75"), 8, Decimal("0.1000"), wins=6)),
            _fold(3, _candidates("total_goals", "over", Decimal("2.75"), 8, Decimal("0.1000"), wins=5)),
            _fold(4, _candidates("total_goals", "over", Decimal("2.75"), 8, Decimal("0.1000"), wins=5)),
            _fold(5, _candidates("total_goals", "over", Decimal("2.75"), 8, Decimal("0.1000"), wins=4)),
        ],
        thresholds=("0.10",),
    )

    text = format_baseline_model_consensus_signal_research_report(report)

    assert "# Baseline Model Consensus Signal Research" in text
    assert "| Rating | Candidates |" in text
    assert "| Signal bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI |" in text
    assert "## Promotion Recommendation" in text


def _fold(index: int, candidates: list[ModelConsensusCandidate]) -> ModelConsensusFoldCandidateSet:
    return ModelConsensusFoldCandidateSet(
        fold_index=index,
        train_rows=20,
        validation_rows=20,
        candidates=candidates,
    )


def _candidates(
    market_type: str,
    side: str,
    line: Decimal,
    count: int,
    raw_edge: Decimal,
    *,
    wins: int,
    calibrated_side: str | None = None,
    calibrated_edge: Decimal = Decimal("0.0200"),
) -> list[ModelConsensusCandidate]:
    candidates = []
    for index in range(count):
        won = index < wins
        candidates.append(
            ModelConsensusCandidate(
                match_id=f"{market_type}-{side}-{line}-{index}",
                kickoff_time=f"2026-01-{index + 1:02d}T12:00:00+08:00",
                league_name="League",
                home_team_name="Home",
                away_team_name="Away",
                market_type=market_type,
                line=line,
                side=side,
                odds=Decimal("2.0000"),
                raw_edge=raw_edge,
                calibrated_side=calibrated_side or side,
                calibrated_edge_for_raw_side=calibrated_edge,
                actual_side=side if won else _opposite_side(market_type, side),
                profit=Decimal("1.0000") if won else Decimal("-1.0000"),
            )
        )
    return candidates


def _opposite_side(market_type: str, side: str) -> str:
    if market_type == "total_goals":
        return "under" if side == "over" else "over"
    return "away_cover" if side == "home_cover" else "home_cover"

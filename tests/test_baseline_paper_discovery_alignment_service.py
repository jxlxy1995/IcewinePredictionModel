from decimal import Decimal

from icewine_prediction.baseline_paper_discovery_alignment_service import (
    PaperDiscoveryCandidateSets,
    _candidate_set_alignment_summary,
    format_baseline_paper_discovery_alignment_report,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate


def test_candidate_set_alignment_summary_compares_latest_t15_and_robust_groups():
    latest_candidates = [
        _candidate("1", "asian_handicap", "away_cover", "2.10", True),
        _candidate("2", "asian_handicap", "away_cover", "1.80", False),
    ]
    t15_candidates = [
        _candidate("2", "asian_handicap", "away_cover", "2.00", True),
        _candidate("3", "asian_handicap", "away_cover", "1.90", True),
    ]
    robust_kept_candidates = [
        _candidate("3", "asian_handicap", "away_cover", "1.90", True),
    ]

    summary = _candidate_set_alignment_summary(
        PaperDiscoveryCandidateSets(
            strategy_key="asian_away_cover_hgb_edge_v1",
            display_name="Away cover",
            latest_candidates=latest_candidates,
            t15_candidates=t15_candidates,
            robust_kept_candidates=robust_kept_candidates,
        )
    )

    assert summary.latest.count == 2
    assert summary.latest.profit == Decimal("0.1000")
    assert summary.latest.roi == Decimal("0.0500")
    assert summary.t15_primary.count == 2
    assert summary.t15_primary.profit == Decimal("1.9000")
    assert summary.t15_primary.roi == Decimal("0.9500")
    assert summary.overlap_latest.count == 1
    assert summary.overlap_t15.count == 1
    assert summary.latest_only.count == 1
    assert summary.t15_only.count == 1
    assert summary.robust_kept.count == 1
    assert summary.robust_kept_not_latest.count == 1


def test_format_report_labels_latest_without_calling_t15_disappearing_stale():
    summary = _candidate_set_alignment_summary(
        PaperDiscoveryCandidateSets(
            strategy_key="asian_away_cover_hgb_edge_v1",
            display_name="Away cover",
            latest_candidates=[_candidate("1", "asian_handicap", "away_cover", "2.10", True)],
            t15_candidates=[_candidate("2", "asian_handicap", "away_cover", "1.90", True)],
            robust_kept_candidates=[_candidate("2", "asian_handicap", "away_cover", "1.90", True)],
        )
    )

    text = format_baseline_paper_discovery_alignment_report(
        _report_with_summary(summary)
    )

    assert "latest-only" in text
    assert "T15-only" in text
    assert "stale" not in text.lower()


def _report_with_summary(summary):
    from pathlib import Path

    from icewine_prediction.baseline_paper_discovery_alignment_service import (
        BaselinePaperDiscoveryAlignmentReport,
    )

    return BaselinePaperDiscoveryAlignmentReport(
        csv_path=Path("local_data/training/dynamic.csv"),
        row_count=100,
        train_rows=80,
        validation_rows=20,
        latest_available_rows=20,
        t15_available_rows=18,
        missing_latest_rows=0,
        missing_t15_rows=2,
        source_name="oddspapi",
        bookmaker="pinnacle",
        execution_targets=(25, 20, 15, 10, 5),
        primary_target=15,
        tolerance_minutes=5,
        strategy_summaries=[summary],
        candidate_sets=[],
    )


def _candidate(
    match_id: str,
    market_type: str,
    side: str,
    odds: str,
    won: bool,
) -> SandboxCandidate:
    return SandboxCandidate(
        match_id=match_id,
        kickoff_time="2026-05-20T20:00:00+00:00",
        league_name="League",
        home_team_name="Home",
        away_team_name="Away",
        market_type=market_type,
        line=Decimal("-0.50"),
        side=side,
        odds=Decimal(odds),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1000"),
        actual_side=side if won else "home_cover",
        profit=(Decimal(odds) - Decimal("1")).quantize(Decimal("0.0001")) if won else Decimal("-1.0000"),
    )

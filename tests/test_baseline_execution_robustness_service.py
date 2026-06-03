from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_execution_robustness_service import (
    ExecutionRobustnessCandidateProfile,
    _build_candidate_profile,
    _strategy_robustness_summary,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.paper_strategy_registry import DEFAULT_STRATEGY


def test_build_candidate_profile_marks_stable_window_as_strong():
    primary = _candidate("1", "away_cover", "-0.50", "0.1200", "1.95", True)
    observations = {
        25: _candidate("1", "away_cover", "-0.50", "0.1000", "1.98", True),
        20: _candidate("1", "away_cover", "-0.50", "0.1100", "1.96", True),
        15: primary,
        10: _candidate("1", "away_cover", "-0.50", "0.0900", "1.94", True),
        5: _candidate("1", "away_cover", "-0.50", "0.0800", "1.92", True),
    }

    profile = _build_candidate_profile(
        DEFAULT_STRATEGY,
        primary,
        observations_by_target=observations,
        execution_targets=(25, 20, 15, 10, 5),
    )

    assert profile.level == "strong"
    assert profile.seen_count == 5
    assert profile.min_edge == Decimal("0.0800")
    assert profile.edge_range == Decimal("0.0400")
    assert profile.side_changed is False
    assert profile.bucket_changed is False


def test_build_candidate_profile_rejects_side_change_even_when_primary_edge_is_high():
    primary = _candidate("2", "away_cover", "-0.50", "0.1600", "1.95", False)
    observations = {
        25: _candidate("2", "away_cover", "-0.50", "0.1300", "1.96", False),
        20: _candidate("2", "home_cover", "-0.50", "0.1200", "1.90", True),
        15: primary,
        10: _candidate("2", "home_cover", "-0.50", "0.1100", "1.88", True),
        5: _candidate("2", "away_cover", "-0.50", "0.0900", "1.94", False),
    }

    profile = _build_candidate_profile(
        DEFAULT_STRATEGY,
        primary,
        observations_by_target=observations,
        execution_targets=(25, 20, 15, 10, 5),
    )

    assert profile.level == "rejected"
    assert profile.side_changed is True


def test_strategy_robustness_summary_groups_level_profit_and_roi():
    profiles = [
        _profile("strong", "1.00"),
        _profile("strong", "-1.00"),
        _profile("candidate", "0.80"),
        _profile("rejected", "-1.00"),
    ]

    summary = _strategy_robustness_summary(DEFAULT_STRATEGY, profiles)

    assert summary.primary_count == 4
    assert summary.level_counts == {"candidate": 1, "rejected": 1, "strong": 2, "watch": 0}
    assert summary.level_profit["strong"] == Decimal("0.0000")
    assert summary.level_roi["strong"] == Decimal("0.0000")
    assert summary.level_profit["candidate"] == Decimal("0.8000")
    assert summary.level_roi["candidate"] == Decimal("0.8000")
    assert summary.level_profit["rejected"] == Decimal("-1.0000")
    assert summary.level_roi["rejected"] == Decimal("-1.0000")


def _profile(level: str, profit: str) -> ExecutionRobustnessCandidateProfile:
    candidate = SandboxCandidate(
        match_id=level,
        kickoff_time="2026-05-20T20:00:00+00:00",
        league_name="League",
        home_team_name="Home",
        away_team_name="Away",
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        side="away_cover",
        odds=Decimal("2.00"),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal("0.1200"),
        actual_side="away_cover" if Decimal(profit) >= 0 else "home_cover",
        profit=Decimal(profit),
    )
    return ExecutionRobustnessCandidateProfile(
        strategy_key=DEFAULT_STRATEGY.strategy_key,
        match_id=candidate.match_id,
        market_type=candidate.market_type,
        primary_candidate=candidate,
        level=level,
        seen_count=5,
        total_points=5,
        min_edge=Decimal("0.0800"),
        max_edge=Decimal("0.1200"),
        edge_range=Decimal("0.0400"),
        side_changed=False,
        line_changed=False,
        bucket_changed=False,
        observed_targets=(25, 20, 15, 10, 5),
    )


def _candidate(
    match_id: str,
    side: str,
    line: str,
    edge: str,
    odds: str,
    won: bool,
) -> SandboxCandidate:
    return SandboxCandidate(
        match_id=match_id,
        kickoff_time="2026-05-20T20:00:00+00:00",
        league_name="League",
        home_team_name="Home",
        away_team_name="Away",
        market_type="asian_handicap",
        line=Decimal(line),
        side=side,
        odds=Decimal(odds),
        model_probability=Decimal("0.6000"),
        market_probability=Decimal("0.5000"),
        edge=Decimal(edge),
        actual_side=side if won else "home_cover",
        profit=(Decimal(odds) - Decimal("1")) if won else Decimal("-1"),
    )

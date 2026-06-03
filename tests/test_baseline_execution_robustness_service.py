from decimal import Decimal
from pathlib import Path

from icewine_prediction.baseline_execution_robustness_service import (
    ExecutionRobustnessCandidateProfile,
    _build_candidate_profile,
    _observation_candidates_by_strategy,
    _profile_from_discovery,
    _strategy_and_observation_candidates_by_strategy,
    _strategy_profiles,
    _strategy_robustness_summary,
)
from icewine_prediction.baseline_recommendation_sandbox_service import SandboxCandidate
from icewine_prediction.paper_recommendation_queue_service import PaperQueueScore
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


def test_strategy_profiles_use_union_discovery_instead_of_primary_only():
    t20_only = _candidate("union", "away_cover", "-0.50", "0.1500", "2.10", True)
    candidates_by_target = {
        25: {DEFAULT_STRATEGY.strategy_key: [_candidate("union", "away_cover", "-0.50", "0.1300", "2.05", True)]},
        20: {DEFAULT_STRATEGY.strategy_key: [t20_only]},
        10: {DEFAULT_STRATEGY.strategy_key: [_candidate("union", "away_cover", "-0.50", "0.1000", "1.95", True)]},
        5: {DEFAULT_STRATEGY.strategy_key: [_candidate("union", "away_cover", "-0.50", "0.0800", "1.90", True)]},
    }

    profiles = _strategy_profiles(
        DEFAULT_STRATEGY,
        candidates_by_target,
        execution_targets=(25, 20, 15, 10, 5),
        primary_target=15,
    )

    assert len(profiles) == 1
    assert profiles[0].primary_candidate == t20_only
    assert profiles[0].seen_count == 4
    assert profiles[0].observed_targets == (5, 10, 20, 25)


def test_strategy_profiles_keep_latest_only_discovery_but_mark_primary_unavailable():
    latest_only = _candidate("latest", "away_cover", "-0.50", "0.1800", "2.20", True)
    candidates_by_target = {
        None: {DEFAULT_STRATEGY.strategy_key: [latest_only]},
    }

    profiles = _strategy_profiles(
        DEFAULT_STRATEGY,
        candidates_by_target,
        execution_targets=(25, 20, 15, 10, 5),
        primary_target=15,
    )

    assert len(profiles) == 1
    assert profiles[0].primary_candidate == latest_only
    assert profiles[0].seen_count == 0
    assert profiles[0].observed_targets == ()


def test_profile_from_discovery_counts_observations_below_discovery_threshold():
    discovered = _candidate("threshold", "away_cover", "-0.50", "0.1500", "2.10", True)
    observations = {
        25: _candidate("threshold", "away_cover", "-0.50", "0.0700", "1.98", True),
        20: _candidate("threshold", "away_cover", "-0.50", "0.0800", "2.00", True),
        15: _candidate("threshold", "away_cover", "-0.50", "0.0900", "2.02", True),
    }

    profile = _profile_from_discovery(
        DEFAULT_STRATEGY,
        discovered,
        observations_by_target=observations,
        primary_target=15,
        execution_targets=(25, 20, 15, 10, 5),
    )

    assert profile.primary_candidate == observations[15]
    assert profile.seen_count == 3
    assert profile.min_edge == Decimal("0.0700")
    assert profile.observed_targets == (15, 20, 25)


def test_observation_candidates_include_rows_below_discovery_threshold():
    row = _research_row(edge_result="win")

    observations = _observation_candidates_by_strategy(
        [row],
        lambda _: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.5700"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.0700"),
            model_name="fake_hgb",
        ),
    )

    strategy_candidates = observations[DEFAULT_STRATEGY.strategy_key]
    assert len(strategy_candidates) == 1
    assert strategy_candidates[0].edge == Decimal("0.0700")
    assert strategy_candidates[0].profit == Decimal("1.0000")


def test_strategy_and_observation_candidates_score_each_row_once():
    calls = 0

    def scorer(_):
        nonlocal calls
        calls += 1
        return PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5000"),
            edge=Decimal("0.1500"),
            model_name="fake_hgb",
        )

    discovered, observations = _strategy_and_observation_candidates_by_strategy(
        [_research_row(edge_result="win")],
        scorer,
    )

    assert calls == 1
    assert discovered[DEFAULT_STRATEGY.strategy_key][0].edge == Decimal("0.1500")
    assert observations[DEFAULT_STRATEGY.strategy_key][0].edge == Decimal("0.1500")


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


def _research_row(*, edge_result: str) -> dict[str, str]:
    return {
        "match_id": "7",
        "source_match_id": "7",
        "league_name": "League",
        "kickoff_time": "2026-05-20T20:00:00+00:00",
        "home_team_name": "Home",
        "away_team_name": "Away",
        "asian_handicap_close_line": "-0.50",
        "asian_handicap_home_odds": "1.900",
        "asian_handicap_away_odds": "2.000",
        "target_asian_handicap_home_result": "loss" if edge_result == "win" else "win",
        "target_asian_handicap_away_result": edge_result,
        "total_goals_close_line": "",
        "total_goals_over_odds": "",
        "total_goals_under_odds": "",
        "target_total_goals_over_result": "",
        "target_total_goals_under_result": "",
    }

# Paper Multi-Timepoint Discovery Design

## Goal

Unify paper candidate discovery for scheduled matches and finished historical backfill. Both flows should simulate the same pre-match operation: discover candidates from standard pre-kickoff odds timepoints, keep only candidates that pass the selected robustness rule, and discard the rest before they become paper candidates.

This replaces the current split where scheduled matches are hard-filtered but finished historical windows keep filtered candidates for inspection.

## Context

The current paper queue can use oddspapi historical snapshots and selected execution robustness rules, but discovery still starts from a single primary snapshot in important paths. Research reports have shown that `latest`, `T-15`, and robust-kept discovery can produce different candidate pools.

The first implementation should avoid a broad taxonomy such as `robust`, `timing_divergent`, and `weak`. The live workflow only needs a practical first rule:

- If any standard timepoint discovers a strategy candidate, evaluate that strategy across the standard execution timepoints.
- If the selected robustness rule passes, keep the candidate.
- If the selected robustness rule fails, discard the candidate.

## Standard Timepoints

Use these discovery timepoints:

- `T-25`
- `T-20`
- `T-15`
- `T-10`
- `T-5`
- `latest`

For fixed targets, select the paired market snapshot inside a `+/-5` minute window around the target. If multiple pairs are available, choose the pair closest to the target time, then prefer a pair at or before the target time, then prefer the lower balance gap. If no pair exists inside the window, that market is unavailable for that target.

`latest` means the latest paired market snapshot at or before kickoff for each market. It participates in discovery, but the selected robustness rule continues to evaluate the fixed execution targets unless a later explicit design changes that.

## Candidate Discovery

For each match:

1. Load oddspapi historical snapshots once.
2. Build one feature row for each available standard timepoint.
3. Run the cached paper scorer on each feature row.
4. Apply every strategy in `paper_strategy_registry.py` to each score.
5. Union discovered observations by `match_id + strategy_key + market_type + side`.
6. For each union candidate, evaluate all fixed target observations for that strategy using `DEFAULT_SELECTED_ROBUSTNESS_RULES`.
7. Emit a queue row only when the rule passes.

If multiple observations in the same union group pass, choose a stable representative row with this preference:

1. Primary target observation when available.
2. The highest-edge fixed target observation.
3. The highest-edge `latest` observation.

The representative row supplies display odds, line, edge, and recommendation text. Robustness fields still describe the fixed-target evaluation.

## Strategy Rules

All strategies should use normal filtering in this workflow. `total_goals_hgb_confirmed_under_mid_275_v1` should no longer be `observe`; it should use the same selected robustness rule behavior as the other strategies.

The first version should not add strategy-level discard reports. If a strategy is weak under this new generation method, it can be re-run and removed in a later explicit task.

## Scheduled And Finished Behavior

Scheduled and finished flows must consume the same discovery result.

For both match statuses:

- Passing candidates are returned as `status == "candidate"`.
- Failing candidates are not returned as paper candidates.
- Batch record creation continues to record only `status == "candidate"`.

The purpose of finished backfill is to simulate what the live scheduled workflow would have done before kickoff. Finished backfill should therefore discard the same non-robust candidates instead of preserving them for manual inspection.

## Diagnostics

Keep diagnostics simple in the first version.

The paper queue report should expose a match-level discard count:

- number of matches with at least one discovered candidate that was discarded by robustness filtering

This may be part of the report payload, formatted report, or a compact diagnostics object. It does not need a per-strategy ROI table or a detailed discard reason breakdown in the first implementation.

Rows returned to the UI should keep the existing robustness fields for retained candidates where available:

- `robustness_mode`
- `robustness_status`
- `robustness_primary_target`
- `robustness_seen_count`
- `robustness_min_edge`
- `robustness_observed_targets`

## Performance Constraints

The new flow increases scoring work from roughly one snapshot per match to at most six standard timepoints per match. That cost is acceptable only if the implementation avoids avoidable repeated work.

Required implementation constraints:

- Train or load the paper scorer once per queue build.
- Load historical snapshots once per match batch and group them by match once.
- Build team prior states once for the match batch.
- Pair and select market snapshots once per match/timepoint rather than inside each strategy.
- Run the scorer at most once per available timepoint feature row.
- Reuse strategy observations for both discovery and robustness evaluation.
- Short-circuit matches with no usable historical snapshots.

The expected cost profile should be close to `number_of_matches * available_timepoints`, not `number_of_matches * timepoints * strategies * repeated_snapshot_scans`.

Focused tests should include a small guard that the scorer is called no more than once per available timepoint for a match.

## Acceptance Criteria

- Scheduled queue and finished historical backfill call the same multi-timepoint discovery path.
- A candidate discovered only by `latest` can enter the observation pool, but must still pass the selected fixed-target robustness rule before it is returned.
- Finished backfill discards non-robust candidates the same way scheduled queue does.
- `total_goals_hgb_confirmed_under_mid_275_v1` uses filter mode instead of observe mode.
- The report exposes a simple count of matches with discovered candidates discarded by robustness filtering.
- Existing batch record behavior still records only `status == "candidate"` rows.
- Tests cover union discovery, fixed-target robustness filtering, scheduled/finished parity, confirmed-under filter mode, and the scorer-call performance guard.

# Total Goals v3 Signal Research Design

## Goal

Build a research-only report for candidate total-goals HGB v3 signals. The report must identify whether any direction and total-line bucket combinations deserve promotion into the paper recommendation workflow, but it must not register or record a new paper strategy by itself.

## Context

The current paper workflow has one total-goals signal: `total_goals_hgb_bucket_v2`. It uses the `raw_hgb_team_form_plus_all_markets` scorer and currently focuses on `over@mid_2.75` and `under@mid_2.75` with an edge threshold of `0.0800`.

The next step is to explore whether adjacent total-line buckets contain stable opportunities. The existing v2 signal remains the production/paper workflow baseline until the user explicitly approves a promotion.

## Candidate Space

The v3 research report evaluates:

- Market: `total_goals`
- Model: `raw_hgb_team_form_plus_all_markets`
- Sides: `over`, `under`
- Total-line buckets: `low_<=2.25`, `mid_2.50`, `mid_2.75`, `high_>=3.00`
- Threshold grid: `0.0600`, `0.0800`, `0.1000`, `0.1200`, `0.1500`, `0.1800`, `0.2000`
- Walk-forward defaults: train ratio `0.6000`, validation ratio `0.1000`, fold count `5`

## Acceptance Gate

A candidate can be labelled `promotable` only when all of these are true:

- Bets are at least `30`.
- At least `4` of `5` folds have positive ROI.
- Total ROI is at least `0.0500`.
- Worst fold ROI is at least `-0.2000`.

Candidates that are close but miss one gate are labelled `watchlist`. Weak or unstable candidates are labelled `rejected`.

## Overlap Guard

The report must compare every candidate against the current v2 bucket rule:

- `over@mid_2.75` threshold `0.0800`
- `under@mid_2.75` threshold `0.0800`

For each candidate, include:

- overlap bet count
- overlap share of the candidate
- incremental bet count outside the current v2 rule
- incremental ROI outside the current v2 rule

If a candidate heavily overlaps v2, it should be described as a possible replacement or threshold adjustment, not an independent confidence signal.

## Outputs

The report should include:

- A summary table of promotable, watchlist, and rejected counts.
- A ranked candidate table by rating, ROI, stability, and bet count.
- A side and bucket overview.
- A comparison to the existing `total_goals_hgb_bucket_v2`.
- A short recommendation section that names which candidates should be promoted, watched, or rejected.

## Workflow Boundary

This work may add a research service, CLI command, training-orchestration report, and tests. It must not modify `paper_strategy_registry.py`, paper recommendation queue registration, paper record insertion, or settlement logic.

After the report is generated, Codex must show the user the relevant data and explain the promotion rationale. A candidate can enter the current paper workflow only after explicit user confirmation.

## Future Sequence

After total-goals v3 research, the next research tracks are:

1. Asian handicap home-side signal research.
2. Model consensus/divergence signals using goal-distribution or alternative model families.

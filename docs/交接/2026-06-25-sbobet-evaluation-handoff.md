# 2026-06-25 SBOBet Evaluation Handoff

## Why this exists

Oddspapi unexpectedly moved `pinnacle` behind a B2B-only option. This branch explored `sbobet` as a temporary fallback while preserving the ability to switch back to `pinnacle` immediately if Oddspapi restores an acceptable plan.

## Durable code changes kept

- Oddspapi fetch/backfill/worker/probe flows now accept an explicit `--bookmaker`, but still default to `pinnacle`.
- Worker-process launch correctly propagates `--bookmaker` into the background worker command.
- SBOBet historical parsing is bookmaker-scoped and does not overwrite Pinnacle rows.
- SBOBet execution-timepoint tolerance is widened to `±10` minutes; default flows remain `±5`.
- Two reusable audit commands were added:
  - `python -m icewine_cli samples bookmaker-overlap-comparison ...`
  - `python -m icewine_cli samples bookmaker-replay-comparison ...`

## Safety constraints confirmed

- Existing `pinnacle` historical odds were not overwritten.
- Default web/API/training/sample behavior remains `pinnacle`.
- SBOBet only participates when explicitly requested.

## Main SBOBet findings

### Single-match verification

Using local `match_id=14279`, Oddspapi could return SBOBet market definitions including Asian handicap. Historical payloads were available, and SBOBet could supply the needed market family, but the standard target timestamps were less dense than Pinnacle. For SBOBet we accepted a `±10` minute window around the main checkpoints, especially for `T-60/T-30/T-25/T-20/T-15/T-10`.

### Overlap audit

Report:
- `local_data/reports/pinnacle_vs_sbobet_overlap_final_v4.md`

Headline numbers:
- baseline samples: `6152`
- candidate samples: `211`
- overlap samples: `210`
- coverage ratio: `0.0341`

Interpretation:
- `total_goals` was relatively close to Pinnacle.
- `match_winner` line structure was effectively aligned.
- `asian_handicap` showed much larger line drift and needs caution.

### Replay comparison audit

Report:
- `local_data/reports/pinnacle_vs_sbobet_replay_comparison_final_v4.md`

Headline numbers:
- overlap matches: `53`
- baseline candidates: `45`
- sbobet candidates: `58`
- overlap candidates: `23`

Interpretation:
- SBOBet is workable enough to flow through downstream candidate-generation logic.
- But Asian handicap behavior diverges materially enough that it should not be treated as a clean Pinnacle replacement without more validation.

## Safe worker result on 2026-06-25

Worker log:
- `logs/odds/20260625-025541-oddspapi-worker-process.log`

Progress snapshot:
- `logs/odds/oddspapi-worker-progress.json`

Observed outcome:
- worker status finished normally; it did not crash
- processed matches: `46`
- matched matches: `120`
- failed matches: `74`
- inserted snapshots: `6504`
- skipped existing odds: `4022`
- requests used: `121`
- dominant failure type: `historical-odds` `404`

Important interpretation:
- This was not mainly an alias problem.
- The repeated pattern was:
  1. fixture matched
  2. `markets` returned successfully
  3. `historical-odds` returned `404`
- So the main SBOBet risk inside Oddspapi is historical availability by league/time window, not fixture matching.

Leagues with many `404` responses included:
- Chile Primera División
- Finland Veikkausliiga
- Sweden Allsvenskan
- Sweden Superettan
- Norway Eliteserien / 1. Division
- Japan J1
- K League 1 / K League 2
- MLS

## Current product judgment

If forced to use SBOBet temporarily:

- It is good enough to keep the code path alive and run controlled audits.
- `total_goals` looks much safer than `asian_handicap`.
- A full temporary switch away from Pinnacle should be considered high-risk unless there is no near-term commercial path to keep Pinnacle.

## Best next step for a new conversation

The next conversation should likely focus on one of these tracks:

1. Evaluate a different third-party structure for Pinnacle-compatible data ingestion with minimal interface churn.
2. Produce a structured `historical-odds 404` fixture list for Oddspapi support, using the June 25 worker log as evidence.
3. Design a bookmaker-adapter boundary so alternative providers can feed the existing historical snapshot schema with the least downstream disruption.

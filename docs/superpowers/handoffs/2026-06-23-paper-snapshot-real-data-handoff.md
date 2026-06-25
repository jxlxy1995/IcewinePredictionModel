# Paper Snapshot Real Data Handoff

Date: 2026-06-23

## Purpose

This handoff is for the lead worker that has access to the real local database and the user's real paper-tracking history.

The current codebase can now persist paper recommendation group snapshots. The missing step is to validate and populate these snapshots against real paper records. This must be done on the real data side because this workspace cannot inspect the user's actual paper records, actual small-stake participation log, or local database state.

## Current Decision Context

- `paper_recommendation_records` are the signal facts for the current paper chain.
- `paper_recommendation_group_snapshots` are the frozen execution-advice layer.
- A snapshot freezes the grouped confidence score, suggested stake, signal set, source, and version used for replay.
- `historical_backfill` is acceptable as a mapping of the user's past real paper-record data. It should still be marked as backfilled because it was not created at the original Web/Bark execution time.
- Do not migrate old `recommendation_records` as part of this validation.
- If source distinction is needed for analysis, prefer time-window filtering first. The current user preference is not to add source filtering yet.

## Commands To Run On Real Data

Run these from the repository root with the same Python environment used by the Web/automation process:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONIOENCODING='utf-8'
```

First inspect the candidate snapshot count without writing rows:

```powershell
python -m icewine_prediction.cli records snapshots-backfill `
  --from-date 2026-04-01 `
  --to-date 2026-06-23 `
  --dry-run
```

Adjust the dates to match the real paper-record period. The date filters are based on `PaperRecommendationRecord.kickoff_time`, using the inclusive match kickoff window.

If the dry-run numbers look reasonable, write the backfilled snapshots:

```powershell
python -m icewine_prediction.cli records snapshots-backfill `
  --from-date 2026-04-01 `
  --to-date 2026-06-23
```

Then build the snapshot report:

```powershell
python -m icewine_prediction.cli records snapshot-report `
  --from-date 2026-04-01 `
  --to-date 2026-06-23
```

The report date filters are also based on the representative paper record's `kickoff_time`, not snapshot creation time. This keeps the CLI report aligned with the web snapshot review page and with period-based review of historical paper records.

## Expected Checks

Before writing snapshots:

- Confirm `candidate_groups` is plausible relative to the number of existing paper records.
- Confirm `created` is nonzero if this is the first backfill for that period.
- Confirm `skipped` is expected if the command has already been run for the same source/version/signal set.
- Confirm no unexpected exception occurs during schema initialization.

After writing snapshots:

- Re-run the same `snapshots-backfill --dry-run` command.
- Expected: `created=0` and `skipped` should account for already-created groups.
- Run `snapshot-report` and inspect:
  - total group count
  - settled group count
  - weighted profit and weighted ROI
  - `market_type + line_bucket`
  - `market_type + stake_bucket`
  - `snapshot_source`

The important report rule is that weighted profit uses frozen `suggested_stake_units` from the snapshot, not a stake recalculated by the current strategy code.

## Real-Data Judgments For The Lead Worker

The lead worker should decide these points with access to the real data:

- Whether the backfilled snapshot count matches the user's expected paper-record history.
- Whether records that the user treated as real small-stake participation are fully represented.
- Whether any paper records are missing settlement, odds, scores, or line buckets.
- Whether the reported profit/ROI matches the user's own external participation log closely enough.
- Whether the current strategy should continue unchanged, be monitored longer, or be adjusted.
- Whether the Web paper tracking page should later display snapshot-based weekly/monthly profit and ROI.

Do not infer strategy quality from the code-only workspace. One or two months of data may still be too small for stake-policy changes.

## Anomaly Checklist

Investigate before trusting the report if any of these appear:

- `candidate_groups=0` for a period that should contain many paper records.
- Very high `skipped` on the first backfill run.
- Snapshot report group count much lower than expected paper activity.
- Large mismatch between flat and weighted profit that cannot be explained by frozen stake sizing.
- Missing or strange `market_type + line_bucket` groups.
- Total-goals 2.5 and Asian-handicap 2.5 being interpreted together outside the market-aware buckets.
- Many unsettled records for matches that should already have final scores.

## Follow-Up Work Suitable For The Code-Only Side

These can be done without real data:

- Add CSV or Markdown export for snapshot reports.
- Add backend summary helpers for future Web display.
- Add tests for additional date-window and edge-case reporting behavior.
- Add Web UI only after the lead worker confirms the real snapshot report is trustworthy.

## Follow-Up Work That Should Stay With The Real-Data Side

These should stay with the lead worker:

- Running real backfill and report commands.
- Comparing report output against the user's actual participation ledger.
- Deciding whether historical backfilled rows should be treated as part of formal tracking.
- Deciding whether to adjust stake policy.
- Deciding whether the Web page should expose weekly/monthly ROI from snapshot data.

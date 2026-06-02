# Paper Confidence Shadow Staking Design

## Goal

Add a paper-only confidence and stake simulation layer for recommendation signals.

The existing paper workflow should continue to show each strategy signal independently with a flat 1-unit stake. A new grouped simulation view should combine same-direction signals into one shadow recommendation, calculate a confidence score, map it to a suggested stake between 0.5 and 3.0 units in 0.25-unit steps, and report simulated weighted results.

Formal recommendation records are out of scope for the first implementation. The scoring output should be designed so it can be reused later, but it should not drive formal recommendations yet.

## Current Context

The paper tracking loop already supports:

- match sync
- result sync
- odds sync
- paper candidate generation
- paper record creation
- paper settlement
- strategy-level ROI reporting

There are currently three active paper signals:

- `asian_away_cover_hgb_edge_v1`
- `asian_away_cover_hgb_bucket_v2`
- `total_goals_hgb_bucket_v2`

`asian_away_cover_hgb_bucket_v2` is an advanced version of `asian_away_cover_hgb_edge_v1`, so those two signals are related and should not be counted as fully independent confidence votes.

Existing paper record duplicate detection uses `match_id + strategy_key + market_type + side + active status`. This allows parallel strategy records for the same match and side, which should remain useful for strategy-level reporting.

## Reporting Model

Keep two reporting perspectives.

### Strategy View

This view preserves current behavior.

- Source: raw `paper_recommendation_records`
- One row per recorded strategy signal
- Settlement: existing flat 1-unit `profit_units`
- Grouping: strategy, league, line bucket, manual adjustment
- Purpose: measure each signal's independent hit rate, profit, ROI, and sample size

This view intentionally allows the same match and betting direction to appear multiple times when multiple strategy signals fired.

### Same-Direction Simulation View

This is the new shadow staking view.

- Source: raw paper records grouped into shadow recommendation groups
- Grouping key: `match_id + market_type + logical_side`
- One group represents one simulated bettable direction
- Each group stores or computes:
  - triggered strategy keys
  - triggered strategy display names
  - signal families
  - representative market line
  - representative odds
  - representative recommendation text
  - confidence score
  - suggested stake units
  - stake cap reason
  - flat 1-unit profit
  - weighted simulated profit

This view should not delete or merge raw strategy records. It is a derived layer for paper analysis.

## Logical Side

Use market-specific logical sides:

- Asian handicap:
  - `away_cover`
  - `home_cover`
- Total goals:
  - `over`
  - `under`

For the initial active signals, the main groups will be `asian_handicap/away_cover` and `total_goals/over|under`.

## Representative Line Selection

When several raw records fall into the same group but have different lines or odds, select one representative market for the group.

Use this deterministic priority order:

1. Prefer records that are executable and not voided.
2. Prefer records with complete line and odds values.
3. Prefer the record whose two-sided odds are closest together, when two-sided odds are available.
4. Prefer stronger signal quality:
   - bucket signal over raw edge signal within the same family
   - higher edge
   - higher model probability margin
5. Prefer later `created_at`, then higher record id as a stable fallback.

Two-sided odds means:

- Asian handicap: home odds vs away odds for the selected line
- Total goals: over odds vs under odds for the selected line

If historical two-sided odds cannot be recovered for older records, fall back to signal quality and deterministic time/id ordering.

## Signal Families

Each strategy belongs to a family. Families are used to avoid over-counting correlated signals.

Initial mapping:

| Strategy key | Family |
| --- | --- |
| `asian_away_cover_hgb_edge_v1` | `asian_away_hgb` |
| `asian_away_cover_hgb_bucket_v2` | `asian_away_hgb` |
| `total_goals_hgb_bucket_v2` | `total_goals_hgb` |

Future model or market-structure signals can add new families. Confidence should reward cross-family support more than multiple signals from the same family.

## Confidence Score

Use an internal 0-100 score. The score is a risk-adjusted staking confidence, not a promised win probability.

First implementation should be simple, deterministic, and explainable:

- Base score from representative edge
- Family support bonus
- Same-family strength bonus for stronger versions such as bucket signals
- Context bonus for same-match cross-market signals
- Historical stability bonus when enough settled paper samples exist
- Correlation penalty for related signals in the same family
- Risk penalty for missing two-sided odds, unsupported buckets, manual adjustments, or small samples

The exact weights should be conservative. Early paper samples are too small to justify large stake escalation.

## Stake Mapping

Map confidence score to a suggested stake in 0.25-unit steps.

Suggested initial mapping:

| Score | Suggested stake |
| ---: | ---: |
| `< 55` | 0.00, observe only |
| `55-59` | 0.50 |
| `60-64` | 0.75 |
| `65-69` | 1.00 |
| `70-74` | 1.25 |
| `75-79` | 1.50 |
| `80-84` | 1.75 |
| `85-89` | 2.00 |
| `90-94` | 2.50 |
| `95+` | 3.00 |

Apply conservative caps while samples are small:

- Cap at 1.00 unit when the group has only one family and the family has limited settled history.
- Cap at 1.25 units when the confidence mainly comes from same-family signals.
- Cap at 1.50 units until score buckets show stable positive ROI in paper simulation.

Store or display the cap reason so the user can understand why a high score did not produce a larger stake.

## Settlement And Simulation

Raw strategy records keep their current settlement behavior.

For same-direction groups:

- Flat group profit should use one representative raw settlement result, not the sum of duplicate same-direction strategy records.
- Weighted simulated profit should be `flat_group_profit * suggested_stake_units`.
- Weighted simulated ROI should be `sum(weighted_profit) / sum(suggested_stake_units)` for groups with stake greater than zero.

This avoids double-counting related strategy signals as multiple bets while preserving the strategy-level report.

## Historical Backfill

After implementation, run a non-destructive backfill for records from 2026-05-29 onward.

The backfill should:

- Keep existing paper records.
- Build historical same-direction groups from existing records.
- Add or compute shadow confidence fields.
- Mark generated scores as historical shadow scoring, not as fields that existed at the original record time.
- Leave existing flat 1-unit settlement values unchanged.

An optional replay audit can later compare what the new scorer would have selected against what was actually recorded, but it should not automatically insert missing old records.

## Web Console

Add a separate tab or section in the paper tracking workspace:

- `strategy`: strategy-level records and ROI, displayed as `按策略` in Chinese UI
- `same_direction_simulation`: grouped confidence and dynamic stake simulation,
  displayed as `同方向模拟` in Chinese UI

The grouped simulation table should show:

- match and kickoff time in Beijing time
- market and playable recommendation text
- representative line and odds
- confidence score
- suggested stake
- cap reason
- triggered signals
- signal families
- flat profit
- weighted simulated profit
- status

Summary cards or tables should include:

- group count
- settled group count
- flat simulated ROI
- weighted simulated ROI
- ROI by confidence score bucket
- ROI by suggested stake bucket
- ROI by signal-family combination

## API And Service Boundaries

Add a service for paper confidence and grouping logic. It should not be embedded directly in the web API or frontend.

Suggested responsibilities:

- group raw paper records by same-direction key
- select representative record
- calculate confidence score
- map score to stake
- calculate flat and weighted settlement summaries
- build report payloads for CLI and web console

The web API should expose the computed grouped simulation as part of the paper tracking workspace payload.

## Data Storage

Prefer a derived service first unless persistence is needed for auditability.

If persistence is added, use a separate table for shadow groups or shadow score snapshots rather than overwriting raw strategy records. Raw records remain the source of truth for strategy performance.

For the first implementation, computing groups from existing records on demand is acceptable if performance remains fine on the local database.

## Error Handling

- Missing representative odds should not block grouping; apply a risk penalty and show a cap reason.
- Groups with unsettled records remain pending in simulation.
- Groups whose raw records disagree on settlement should surface a warning and choose the representative record's settlement for flat simulated profit.
- Voided records should be excluded from group selection unless all records in the group are voided.
- Unknown strategy keys should map to an `unknown` family and receive no family bonus.

## Testing

Backend tests should cover:

- v1 and v2 same-match same-side records remain separate in strategy view.
- v1 and v2 same-match same-side records become one simulation group.
- same match but different market or side becomes separate simulation groups.
- representative line selection is deterministic.
- confidence score records same-family support without double-counting it as independent support.
- stake mapping and sample caps.
- weighted ROI uses one grouped flat result, not the sum of duplicate strategy records.
- historical backfill/report generation does not mutate existing flat settlement values.

Frontend tests should cover:

- paper workspace still shows strategy records.
- new same-direction simulation tab renders grouped rows.
- confidence score, suggested stake, triggered signals, and weighted profit display correctly.

## Rollout

1. Implement service and tests for grouping, scoring, stake mapping, and summaries.
2. Add API payload fields for same-direction simulation.
3. Add web tab for grouped simulation.
4. Add CLI or maintenance command for historical shadow scoring/backfill/reporting from 2026-05-29 onward.
5. Run the historical backfill/report locally.
6. Compare strategy ROI vs grouped weighted simulation ROI before considering formal recommendation integration.

## Out Of Scope

- Formal recommendation stake changes.
- Clearing or rebuilding existing paper records.
- Adding new predictive signals or model algorithms.
- Real-money stake automation.

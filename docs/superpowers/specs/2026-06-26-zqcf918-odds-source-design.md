# zqcf918 Odds Source Design

## Goal

Add zqcf918, also known as 足球财富, as a supplemental historical odds source for matches where The Odds API does not support the league or does not return usable Pinnacle odds. The first supported bookmaker is Pinnacle, shown on zqcf918 as 平* with `companyId=87`.

The integration must preserve the existing source priority and avoid overwriting higher priority data. It should also give the operator manual controls to maintain zqcf918 match IDs and backfill selected matches from the web UI.

## Confirmed Product Requirements

- Add a match-list action to sync zqcf918 match IDs for the currently filtered match list, only targeting matches that do not already have a zqcf918 match ID.
- Add a match-list action to sync zqcf918 Pinnacle odds for the currently filtered match list.
- Add a single-match action named around "财富赔率" near the existing single-match odds pull.
- Add a zqcf918 match ID display and edit area on the match detail page, including add/update support when the ID is missing.
- Use `source_name = zqcf918`.
- Use `bookmaker = pinnacle`.
- Source priority should be:
  1. `the_odds_api / pinnacle`
  2. `oddspapi / pinnacle`
  3. `zqcf918 / pinnacle`
  4. `oddspapi / sbobet`
- Web batch actions that affect more than 50 matches should show a confirmation prompt.
- Automation should not be heavily blocked by protective prompts. It should use normal timeout, retry, and failure recording instead.
- Initial validation should include completed-match comparisons before relying on zqcf918 broadly.

## Current System Fit

The existing schema already has the two main primitives needed for this feature:

- `OddsSourceMatch` can store the mapping from local `match_id` to external zqcf918 `matchId`.
- `HistoricalOddsSnapshot` and `HistoricalOddsRawSnapshot` can store zqcf918 odds using distinct `source_name` and `bookmaker` values.

Because of this, the first implementation should avoid a migration unless implementation discovers a strict need for additional audit metadata. Manual versus automatic match ID creation can be represented in `match_reason`.

## zqcf918 Data Access

The sample page:

`https://www.zqcf918.com/zsDetail?matchId=4460916&companyId=87&type=0`

contains static match metadata in the Next.js payload, but the odds timeline itself is loaded through structured POST endpoints. The integration should use those JSON endpoints rather than scraping rendered DOM.

Known request shape:

```json
{
  "params": {
    "matchId": "4460916",
    "companyId": "87"
  }
}
```

Known endpoints:

- Asian handicap: `/new/match/v11/indexNumber/getAsianIndexNumberListByH5`
- Totals: `/new/match/v11/indexNumber/getBallIndexNumberListByH5`
- 1X2: `/new/match/v11/indexNumber/getEuropeIndexNumberListByH5`

Known response shape:

```json
{
  "code": 1,
  "msg": "请求成功",
  "success": true,
  "data": {
    "rollList": [],
    "indexList": [],
    "breakfastList": []
  }
}
```

The client should treat non-success responses, malformed payloads, empty timelines, and request failures as recoverable per-match failures.

## Components

### `zqcf918_client`

Purpose: isolate HTTP access to zqcf918.

Responsibilities:

- Fetch Asian handicap, totals, and 1X2 timelines for a zqcf918 `matchId`.
- Use `companyId=87` by default.
- Provide timeout and small retry support.
- Return typed or well-normalized payloads to the mapper.
- Avoid database writes.

### `zqcf918_odds_mapper`

Purpose: convert zqcf918 timeline rows into the existing historical odds model.

Responsibilities:

- Map zqcf918 Asian handicap rows into existing Asian handicap snapshot fields.
- Map zqcf918 totals rows into existing total goals snapshot fields.
- Map zqcf918 1X2 rows into existing match winner snapshot fields.
- Skip sealed, closed, empty, or non-numeric rows.
- Normalize times to timezone-aware datetimes.
- Select or expose rows so the existing standard execution-timepoint logic can produce T-60, T-30, T-25, T-20, T-15, and T-10 snapshots.
- Preserve raw row payloads for audit.

Known field interpretation:

- Asian handicap and totals rows use `c`, `d`, and `e`.
- For Asian handicap, `c` is the home-side odds, `d` is the line, and `e` is the away-side odds.
- For totals, `c` is the over odds, `d` is the line, and `e` is the under odds.
- For 1X2, `c1`, `c2`, and `c3` are home, draw, and away odds.
- Rows with `isFeng2 = true` or sealed values should be skipped.

Field semantics must still be verified with completed-match comparisons before broad automation is enabled.

### `zqcf918_match_service`

Purpose: manage zqcf918 match ID mappings.

Responsibilities:

- Read the zqcf918 mapping for a local match.
- Upsert a manual zqcf918 `matchId` from the match detail page.
- Discover and store zqcf918 `matchId` values for a filtered match set.
- Store mappings in `OddsSourceMatch` with `source_name = zqcf918`.
- Use `match_confidence` and `match_reason` to distinguish exact/manual/probable/unmatched results.

The automatic discovery endpoint is the main unknown area. The first implementation milestone should include a read-only probe to identify a stable zqcf918 match search or schedule endpoint, then implement matching with conservative confidence thresholds.

### `zqcf918_sync_service`

Purpose: write zqcf918 odds into the existing historical odds tables.

Responsibilities:

- Resolve local match to zqcf918 `matchId`.
- Fetch timelines from `zqcf918_client`.
- Map rows through `zqcf918_odds_mapper`.
- Upsert `HistoricalOddsRawSnapshot` and `HistoricalOddsSnapshot` rows with `source_name = zqcf918` and `bookmaker = pinnacle`.
- Update the `OddsSourceMatch.historical_odds_status`, `historical_odds_checked_at`, and `historical_odds_error` fields.
- Return per-match success, failed, skipped, requests, and credits-like counters matching the existing sync response style.

`credits` should be reported as zero because zqcf918 is not a credit-billed provider in the current design.

## Web API Design

Add endpoints following existing match-list and match-detail sync patterns:

- `POST /api/match-list/sync/zqcf918-match-ids`
  - Input: current match-list filters.
  - Behavior: select current filtered matches, target only rows missing a zqcf918 mapping, discover and store mappings.

- `POST /api/match-list/sync/zqcf918-odds`
  - Input: current match-list filters.
  - Behavior: select current filtered matches and run zqcf918 odds sync.

- `POST /api/matches/{match_id}/sync/zqcf918-odds`
  - Behavior: run zqcf918 odds sync for one match.

- `PUT /api/matches/{match_id}/zqcf918-match-id`
  - Input: zqcf918 `matchId`.
  - Behavior: manual upsert of `OddsSourceMatch`.

Optional if useful:

- `DELETE /api/matches/{match_id}/zqcf918-match-id`
  - Behavior: clear an incorrect manual mapping.

## Frontend Design

### Match List

Add two actions near existing sync controls:

- `同步财富 matchID`
- `同步财富赔率`

Both actions operate on the current filter selection, consistent with existing match-list sync operations.

If the selected match count is greater than 50, show a confirmation prompt before sending the request. This confirmation is only a web UI guard and should not affect automated jobs.

### Match Detail

Add a compact zqcf918 match ID field to the detail view:

- Show the current zqcf918 `matchId`, if present.
- Allow editing and saving.
- Allow adding when missing.
- Prefer showing the zqcf918 detail URL or a copyable ID after a value exists.

Add a `财富赔率` action near the current single-match odds action.

## Automatic Fallback Policy

The default match odds sync should keep The Odds API as the primary path.

After The Odds API runs for a match, the service should check whether that match has trusted historical odds according to the priority list. If not, zqcf918 should be attempted when either:

- The match league is listed in `config/the_odds_api_unsupported_leagues.yaml`.
- The Odds API did not produce usable trusted Pinnacle odds for the match.

After zqcf918 runs, the service should check trusted odds again. If still missing and the league is eligible for existing SBOBet fallback, it can proceed to `oddspapi / sbobet`.

This preserves the intended priority:

`the_odds_api / pinnacle` -> `oddspapi / pinnacle` -> `zqcf918 / pinnacle` -> `oddspapi / sbobet`

## Source Selection Changes

Update odds source selection constants and labels so trusted selection includes zqcf918:

- Add `ZQCF918_SOURCE_NAME = "zqcf918"`.
- Keep `PINNACLE_BOOKMAKER = "pinnacle"`.
- Include zqcf918 in the trusted priority between oddspapi Pinnacle and oddspapi SBOBet.
- Make `source_label_for_snapshots` return a distinct label for `zqcf918 / pinnacle`, such as `zqcf918_pinnacle_historical`.

This ensures match list coverage, execution-timepoint coverage, training sample selection, and recommendation inputs can see zqcf918 data without treating it as oddspapi data.

## Rate Limiting and Failure Handling

The integration should be polite but not overprotective:

- Use a single worker or low concurrency by default.
- Add a small delay between requests in batch jobs if needed after observation.
- Use request timeouts.
- Retry only transient request failures.
- Record per-match failures without aborting the whole batch.
- Reuse existing mappings and avoid repeated match ID discovery when a mapping already exists.
- Do not make web confirmation prompts part of backend automation.

## Validation Plan

Before relying on zqcf918 broadly, implement a small comparison workflow for completed matches:

- Choose known completed matches where The Odds API or oddspapi Pinnacle already has snapshots.
- Fetch zqcf918 Pinnacle timelines for the same matches.
- Compare Asian handicap line and home/away odds at standard timepoints.
- Compare totals line and over/under odds at standard timepoints.
- Compare 1X2 home/draw/away odds.
- Confirm timestamp interpretation between `changeTime` and `changeTimeStr`.
- Confirm sealed rows are excluded correctly.

The implementation should not run broad live odds backfills until these comparisons look sane.

## Testing Plan

Unit tests:

- zqcf918 client request construction.
- zqcf918 mapper handling for Asian handicap, totals, and 1X2.
- Sealed, empty, malformed, and non-numeric row skipping.
- Source priority selection with `zqcf918 / pinnacle`.
- Manual zqcf918 match ID upsert.

Service tests:

- Single-match zqcf918 odds sync writes source/bookmaker correctly.
- Batch match ID sync skips matches with existing zqcf918 mappings.
- Batch odds sync returns per-match success, failed, skipped counters.
- Automatic fallback attempts zqcf918 before SBOBet when The Odds API has no usable trusted odds.
- Higher priority source data remains selected when it exists.

Frontend/API tests:

- Match detail payload includes zqcf918 match ID data.
- Manual edit endpoint updates the detail payload.
- Match-list batch actions send current filters.
- Batch action confirmation appears for more than 50 matches.

## Rollout Plan

1. Build the zqcf918 client and mapper behind tests.
2. Add a completed-match comparison tool or diagnostic path.
3. Add zqcf918 match ID storage, detail display, and manual edit.
4. Add single-match zqcf918 odds sync.
5. Add match-list zqcf918 match ID sync.
6. Add match-list zqcf918 odds sync with the greater-than-50 confirmation.
7. Add zqcf918 to trusted source priority.
8. Add automatic fallback after The Odds API and before SBOBet.

Each step should be independently testable so the integration can stop at manual mode if zqcf918 discovery or odds semantics prove less stable than expected.

## Open Risk

The main unresolved risk is automatic zqcf918 `matchId` discovery. The odds timeline endpoints are straightforward once a match ID is known, but the stable way to search or list zqcf918 matches must still be identified. The first implementation should therefore treat discovery as a probe-driven component and keep manual match ID editing as a required fallback.

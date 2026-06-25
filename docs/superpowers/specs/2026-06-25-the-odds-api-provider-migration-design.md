# The Odds API Provider Migration Design

## Context

Oddspapi has stopped offering the needed Pinnacle subscription path for personal users, so the project will formally switch future odds ingestion to The Odds API. Existing Oddspapi historical data remains valuable and must not be overwritten or mixed with new source data.

The project already stores historical odds with source separation through `source_name` and `bookmaker`. The migration should use that separation instead of renaming or deleting Oddspapi code.

## Goals

- Add The Odds API as the default provider for future Pinnacle odds ingestion.
- Preserve all existing `oddspapi/pinnacle` historical snapshots.
- Store The Odds API snapshots as `source_name="the_odds_api"` and `bookmaker="pinnacle"`.
- Let downstream readers consume Pinnacle odds regardless of source, with source priority `the_odds_api` before `oddspapi`.
- Keep switching to future providers lightweight by isolating provider-specific fetch and mapping code.

## Non-Goals

- Do not backfill old matches already covered by Oddspapi unless explicitly requested later.
- Do not delete existing Oddspapi runners, diagnostics, audits, or worker commands during this migration.
- Do not rewrite training or paper systems around a new database schema.
- Do not blend The Odds API data into `source_name="oddspapi"`.

## Chosen Approach

Use a B-light provider-adapter design. The adapter boundary covers only source-specific work:

- provider configuration
- league or sport-key mapping
- event lookup and match selection
- market payload mapping
- request budgeting and error classification

The shared storage path remains `HistoricalOddsSnapshotInput` plus `store_historical_odds_snapshots`. Existing paper, training, and feature logic should continue to operate on stored snapshots, with focused changes only where source selection is currently hard-coded to Oddspapi.

## Data Storage Strategy

The Odds API snapshots are written independently:

```text
source_name = the_odds_api
bookmaker = pinnacle
```

Existing Oddspapi snapshots remain:

```text
source_name = oddspapi
bookmaker = pinnacle
```

Because `historical_odds_snapshots` and `historical_odds_raw_snapshots` include `source_name` and `bookmaker` in their unique keys, both providers can coexist without overwriting each other.

`odds_source_matches` should also use `source_name="the_odds_api"` for The Odds API event matches. This keeps source event IDs and match status separate from Oddspapi fixture IDs.

## Read Selection Strategy

Downstream odds reads should be changed from "read `source_name=oddspapi`" to "read Pinnacle odds with provider priority".

Default priority:

```text
1. source_name = the_odds_api, bookmaker = pinnacle
2. source_name = oddspapi, bookmaker = pinnacle
```

When both providers have snapshots for a match and required timepoint or market group, readers select The Odds API. When The Odds API does not have usable snapshots, readers may use Oddspapi. If neither provider has the required Pinnacle data, the existing no-odds or fallback behavior applies.

The selection should happen at a small shared helper boundary, not by scattering `OR source_name IN (...)` queries throughout the codebase. Callers that need reproducible old experiments should still be able to pass an explicit single source.

## The Odds API Mapping

The Odds API market keys map to existing internal market types:

```text
h2h     -> match_winner
spreads -> asian_handicap
totals  -> total_goals
```

The mapper should emit `HistoricalOddsSnapshotInput` rows with:

- `source_name="the_odds_api"`
- `source_fixture_id` set to The Odds API event ID
- `bookmaker="pinnacle"`
- `period="full_time"` unless the API payload proves a different period is needed
- `market_id` stable enough to distinguish market type, line, and provider event
- `raw_payload` retained for diagnostics

## League And Event Matching

The Odds API uses sport keys rather than Oddspapi tournament IDs. Add a focused mapping from API-Football league IDs to The Odds API sport keys. Known examples include:

```text
140 -> soccer_spain_la_liga
78  -> soccer_germany_bundesliga
79  -> soccer_germany_bundesliga2
61  -> soccer_france_ligue_one
62  -> soccer_france_ligue_two
98  -> soccer_japan_j_league
292 -> soccer_korea_kleague1
188 -> soccer_australia_aleague
253 -> soccer_usa_mls
262 -> soccer_mexico_ligamx
179 -> soccer_spl
```

Event matching should use kickoff proximity plus normalized home and away team names. It should reuse existing alias infrastructure where practical, but source-specific aliases must use `source_name="the_odds_api"` rather than Oddspapi aliases.

## Fetch Flow

For future unstarted matches:

1. Load candidate API-Football matches.
2. Resolve league ID to The Odds API sport key.
3. Fetch events or odds for the sport key with `bookmakers=pinnacle`, `markets=h2h,spreads,totals`, `oddsFormat=decimal`, and `dateFormat=iso`.
4. Match The Odds API event to the local match.
5. Map available Pinnacle markets to `HistoricalOddsSnapshotInput`.
6. Store snapshots under `the_odds_api/pinnacle`.
7. Record match status in `odds_source_matches`.

For historical or timepoint fetches, use The Odds API historical endpoints at the required target times when available. The standard project timepoints remain `T-60`, `T-30`, `T-25`, `T-20`, `T-15`, and `T-10`, with the existing tolerance and supplement behavior preserved.

## CLI Shape

Add new The Odds API commands parallel to the existing Oddspapi commands:

```text
odds-source the-odds-api-plan
odds-source the-odds-api-fetch
odds-source the-odds-api-match-report
```

Keep existing probe commands. Keep Oddspapi commands available as legacy tools for historical diagnostics and old data maintenance.

Commands should support dry-run or request-budget options before any broad fetch. Clear/delete commands must require explicit `source_name` and should not default to deleting all sources.

## Error Handling

Provider failures should be recorded per match and source:

- `unmatched` for no reliable event match
- `empty` for event found but no relevant Pinnacle markets
- `unavailable` for provider-reported unavailable historical odds
- `failed` for request or mapping errors
- `success` for stored usable snapshots

Error messages must not include API keys. Request budget exhaustion should stop the run cleanly and report progress.

## Testing

Add focused tests for:

- The Odds API market mapping into internal snapshot rows.
- API-Football league ID to The Odds API sport-key mapping.
- Event matching by teams and kickoff time.
- Storage under `source_name="the_odds_api"` without overwriting `oddspapi`.
- Pinnacle source-priority reads choosing The Odds API before Oddspapi.
- Explicit single-source reads still supporting reproducible old Oddspapi experiments.
- CLI option wiring for plan, fetch, and match report commands.

Existing Oddspapi tests should remain valid unless a test is specifically asserting a default read source that is intentionally being generalized to Pinnacle provider priority.

## Rollout

1. Implement provider constants and The Odds API mapper.
2. Implement sport-key mapping and event matcher.
3. Implement The Odds API sync runner using the existing storage path.
4. Add shared Pinnacle odds source-priority read helper.
5. Switch future paper odds reads to the source-priority helper.
6. Leave historical training defaults reproducible, but expose the same priority helper where appropriate.
7. Run a small future-match fetch and inspect market completeness before enabling broader scheduled use.

## Open Decisions

The read strategy is decided: default Pinnacle reads may use any supported source, with `the_odds_api` preferred over `oddspapi` when both are usable.

The implementation still needs to choose exact helper names and module placement based on the surrounding code during the planning phase.

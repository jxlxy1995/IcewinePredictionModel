# Odds Provider Order Design

## Goal

Make Oddspapi/Pinnacle the default odds source while preserving reliable per-match fallback to The Odds API/Pinnacle and zqcf918/Pinnacle. Stop creating or selecting new Oddspapi/SBOBet data.

## Current Problem

The default sync path currently starts with The Odds API/Pinnacle, then tries zqcf918/Pinnacle for unresolved matches, and only uses Oddspapi/SBOBet for a small verified league set. Historical snapshot selection uses a different priority and still includes SBOBet. This makes operational behavior and model input selection inconsistent.

## Design

The shared match odds sync service will use this ordered chain for every eligible match:

1. Oddspapi/Pinnacle
2. The Odds API/Pinnacle
3. zqcf918/Pinnacle

Each later provider receives only matches without a trusted Pinnacle snapshot from an earlier provider. The default provider enum remains available for explicit one-provider runs, but the default entry point is Oddspapi.

Trusted historical snapshot selection will use the same source order. Existing Oddspapi/SBOBet rows and raw payloads remain in the database for audit and historical inspection, but are excluded from trusted selection and never requested by the shared sync path.

Provider result accounting will continue to report requests, credits, retry data, source-match status, and per-match fallback errors. A provider exception must not prevent later providers from attempting unresolved matches.

## Validation

Before changing the default order, run a non-persistent Oddspapi availability comparison for the remaining eight non-cup matches in the 2026-08-25 12:00 through 2026-08-26 12:00 Beijing window. Compare fixture matching, market availability, and rough snapshot coverage with the existing The Odds API/Pinnacle rows. The seven already tested league samples are considered passing, with Argentina and Brazil requiring alias review because their match confidence was 0.50.

## Compatibility

No database migration is required. The change must not delete existing snapshots. Existing explicit `provider=oddspapi` and `provider=the_odds_api` calls remain valid.

## Tests

Unit tests will assert the default provider, ordered fallback behavior, trusted snapshot priority, no SBOBet invocation, preservation of existing SBOBet rows, and provider error propagation when all providers fail.

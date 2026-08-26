# Temporarily Disable Oddspapi Odds Requests Design

## Goal

Temporarily stop new Oddspapi odds requests while retaining the complete integration so it can be restored with a single configuration change after the provider confirms Pinnacle access.

## Design

Add `oddspapi_enabled` to `config/sync.yaml`. The production value is `false` during the provider entitlement investigation. `load_project_settings` reads the flag and defaults it to `true` when older or test configuration files do not define it.

When the shared `run_match_odds_sync_for_session` entry point is called with its default Oddspapi-first provider and the flag is disabled, it skips the Oddspapi request entirely. The existing fallback chain then runs The Odds API for unresolved matches and zqcf918 for any remaining matches. Existing Oddspapi code, mappings, aliases, historical snapshots, and explicit provider APIs remain intact.

The flag applies only to new odds synchronization. Historical snapshot selection is unchanged, so existing trusted Oddspapi/Pinnacle snapshots remain available for training and analysis.

## Error Handling

Disabling Oddspapi must not add a synthetic provider error or consume Oddspapi request budget. The result payload continues to report the actual providers used and existing retry/fallback accounting. If the flag is changed back to `true`, the current Oddspapi-first behavior resumes without code changes.

## Validation

Tests will verify that the disabled setting skips the Oddspapi syncer and still invokes The Odds API and zqcf918 as needed, while an enabled setting preserves the existing Oddspapi-first chain. Settings tests will verify the explicit flag and backward-compatible default.

## Compatibility

No database migration or data deletion is required. The only operational change is the `oddspapi_enabled` value in `config/sync.yaml`.

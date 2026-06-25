# The Odds API Web Automation Sync Design

## Context

The Odds API provider path now exists for CLI experiments and stores Pinnacle snapshots under `source_name="the_odds_api"`. The Web match-list odds buttons, batch odds sync button, and paper automation scheduler still depend on the old match-list odds sync function, which calls Oddspapi directly and checks only `source_name="oddspapi"` for historical odds success.

The next migration step is to move those operational entry points to The Odds API without changing button APIs or overwriting old Oddspapi historical data.

## Goals

- Make the Web match row odds button use The Odds API by default.
- Make the Web batch odds sync button use The Odds API by default.
- Make paper automation odds prefetch use the same The Odds API default path.
- Keep Oddspapi code available as a legacy provider, not as an implicit fallback.
- Keep provider switching lightweight through one small provider-neutral sync boundary.
- Treat usable Pinnacle historical odds as provider-priority data: `the_odds_api` before `oddspapi`.

## Non-Goals

- Do not delete Oddspapi worker, audit, CLI, or mapper code.
- Do not rewrite the frontend API contract.
- Do not overwrite existing `oddspapi/pinnacle` snapshots.
- Do not backfill broad historical seasons in this change.
- Do not add a provider selection UI in this change.

## Chosen Approach

Add a focused provider-neutral match odds sync service. Web and automation will call this service instead of calling a provider runner directly.

The default provider is `the_odds_api`. The service will route by provider name:

```text
web/automation odds sync
  -> match odds sync service
     -> the_odds_api runner by default
     -> oddspapi runner only when explicitly requested by code/config later
```

The service returns the existing Web sync result shape:

```text
{
  "success": [{"match_id": 1, "message": "..."}],
  "failed": [{"match_id": 2, "message": "..."}],
  "skipped": [{"match_id": 3, "message": "..."}],
  "requests": 4
}
```

This keeps frontend and scheduler call sites stable.

## The Odds API Runtime Behavior

For selected matches, group by season because existing runner APIs are season-based. For each season:

1. Call the The Odds API runner with the requested match IDs.
2. Store any returned snapshots as `the_odds_api/pinnacle`.
3. Mark a match successful when it has usable Pinnacle historical odds from a priority-supported source.
4. Mark a match failed when no usable Pinnacle historical odds exist after the run.

The implementation should not call API-Football live odds fallback from the default The Odds API path. The prior fallback can remain in legacy Oddspapi code if needed later, but it should not make the new default path ambiguous.

## Passed-Kickoff Matches

The Web and automation workflows may request odds for matches that are already in play or finished. These requests should aim to fetch pre-match Pinnacle odds.

This change will extend The Odds API sync runner with a historical fetch path for matches whose kickoff time is not in the future. The historical path should request The Odds API historical odds around a pre-kickoff target time and map the returned event through the same mapper.

Initial target selection:

```text
T-10 minutes before kickoff
```

This single target is enough for operational Web/automation odds availability. Broader multi-timepoint historical backfill remains a separate task.

## Success Detection

Success detection should use a shared helper that checks for historical snapshots matching:

```text
bookmaker = pinnacle
source_name in (the_odds_api, oddspapi)
```

This helper should use the existing source priority constants and must not scatter hard-coded source checks through Web sync code.

If both providers exist for a match, downstream readers already prefer `the_odds_api`; this change aligns Web sync success detection with that policy.

## Error Handling

- Missing season means the match is skipped.
- Unsupported league sport key means the match fails with a clear message or is recorded by the runner as unmatched.
- The Odds API request errors are returned in `failed`.
- Request budget exhaustion stops the run and reports progress from completed matches.
- API keys must not appear in errors.

## Testing

Add tests for:

- The provider-neutral sync service calls The Odds API by default and reports success using `the_odds_api/pinnacle`.
- The service does not treat old Oddspapi as overwritten data.
- Web default odds syncer routes through the provider-neutral service.
- The The Odds API sync client can call the historical odds endpoint with the correct timestamp parameter.
- The The Odds API runner uses historical fetch for passed-kickoff matches and stores snapshots under `the_odds_api/pinnacle`.

Existing frontend tests should not need changes because endpoint request and response shapes stay stable.

# The Odds API Web Automation Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Web match odds buttons, batch odds sync, and paper automation odds sync through The Odds API by default while keeping provider switching lightweight.

**Architecture:** Add a small provider-neutral match odds sync service that returns the existing Web result shape. The service defaults to The Odds API, keeps Oddspapi as an explicit legacy provider, and uses shared Pinnacle source-priority checks for success detection.

**Tech Stack:** Python, SQLAlchemy ORM, FastAPI, pytest, existing The Odds API client and historical odds storage services.

---

### Task 1: Provider-Neutral Match Odds Sync Service

**Files:**
- Create: `src/icewine_prediction/match_odds_sync_service.py`
- Test: `tests/test_match_odds_sync_service.py`

- [ ] **Step 1: Write failing tests**

Create tests that seed matches and snapshots, then assert the new service defaults to The Odds API and returns the Web sync result shape.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_odds_sync_service.py -q
```

Expected: FAIL because `icewine_prediction.match_odds_sync_service` does not exist.

- [ ] **Step 3: Implement minimal service**

Create a service with:

- `MatchOddsSyncProvider` constants for `the_odds_api` and `oddspapi`.
- `run_match_odds_sync(...)` returning `success`, `failed`, `skipped`, and `requests`.
- `has_priority_pinnacle_historical_odds(session, match_id)` using `PINNACLE_SOURCE_PRIORITY` and `PINNACLE_BOOKMAKER`.
- explicit legacy Oddspapi routing, but default The Odds API routing.

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_odds_sync_service.py -q
```

Expected: PASS.

### Task 2: The Odds API Historical Fetch For Passed-Kickoff Matches

**Files:**
- Modify: `src/icewine_prediction/the_odds_api_sync_runner.py`
- Test: `tests/test_the_odds_api_sync_runner.py`

- [ ] **Step 1: Write failing tests**

Add tests asserting:

- `TheOddsApiSyncClient.fetch_historical_odds(...)` calls `sports/{sport_key}/odds-history` with `date`.
- `run_the_odds_api_sync_for_session(...)` uses historical odds for a match whose kickoff time is in the past.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_the_odds_api_sync_runner.py -q
```

Expected: FAIL because the historical fetch method and runner branch do not exist.

- [ ] **Step 3: Implement minimal historical branch**

Add:

- `TheOddsApiSyncClient.fetch_historical_odds(sport_key, snapshot_time)`
- a helper that chooses `kickoff_time - 10 minutes`
- runner logic that calls current odds for future matches and historical odds for passed-kickoff matches

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_the_odds_api_sync_runner.py -q
```

Expected: PASS.

### Task 3: Wire Web And Automation Default Syncer

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] **Step 1: Write failing tests**

Update or add tests showing `create_web_app()` defaults `match_list_odds_syncer` to the provider-neutral The Odds API service and that endpoints keep the same response shape.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q
```

Expected: FAIL because Web still calls `_run_match_list_odds_sync`.

- [ ] **Step 3: Replace default wiring**

Change `create_web_app()` so default `match_list_odds_syncer` is the provider-neutral service. Keep `_run_match_list_odds_sync` only if tests or legacy references still need it, or simplify it to call the new service.

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_odds_sync_service.py tests/test_the_odds_api_sync_runner.py tests/test_web_console_api.py -q
```

Expected: PASS.

### Task 4: Final Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run focused migration tests**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_odds_sync_service.py tests/test_the_odds_api_sync_runner.py tests/test_oddspapi_sync_cli.py tests/test_web_console_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint if available**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m ruff check src tests
```

Expected: PASS if ruff is installed; otherwise record that ruff is unavailable.

- [ ] **Step 3: Inspect git diff**

Run:

```powershell
git diff --stat
git diff -- src/icewine_prediction/match_odds_sync_service.py src/icewine_prediction/the_odds_api_sync_runner.py src/icewine_prediction/web_api.py
```

Expected: Diff only contains provider sync routing, historical The Odds API support, and tests/docs for this change.

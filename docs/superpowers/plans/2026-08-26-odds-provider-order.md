# Odds Provider Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Oddspapi/Pinnacle the default source with ordered per-match fallback to The Odds API/Pinnacle and zqcf918/Pinnacle, while retiring Oddspapi/SBOBet from trusted selection and new syncs.

**Architecture:** Centralize the operational provider order in `match_odds_sync_service.py`. Keep source-specific syncers unchanged and run each subsequent sync only for matches that still lack a trusted Pinnacle snapshot. Make `odds_provider_selection_service.py` use the same Pinnacle-only priority and preserve old SBOBet rows as non-trusted audit data.

**Tech Stack:** Python, SQLAlchemy, pytest, Typer CLI.

---

### Task 1: Lock the selection and fallback contract with tests

**Files:**
- Modify: `tests/test_odds_provider_selection_service.py`
- Modify: `tests/test_match_odds_sync_service.py`

- [ ] **Step 1: Add failing selection tests**

Assert `PINNACLE_SOURCE_PRIORITY` and `TRUSTED_SNAPSHOT_PRIORITY` are Oddspapi/Pinnacle, The Odds API/Pinnacle, and zqcf918/Pinnacle in that order, and assert an existing SBOBet-only row is not selected.

- [ ] **Step 2: Add failing sync-order tests**

Create fakes for all three providers. Assert the default call order is Oddspapi, then The Odds API for unresolved IDs, then zqcf918 for remaining IDs. Assert `bookmaker="sbobet"` is never passed and old SBOBet rows are not deleted.

- [ ] **Step 3: Run the focused tests and confirm they fail for the old behavior**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_odds_provider_selection_service.py tests/test_match_odds_sync_service.py -q
```

Expected: failures showing the old provider priority and default The Odds API path.

### Task 2: Implement the ordered provider chain

**Files:**
- Modify: `src/icewine_prediction/odds_provider_selection_service.py`
- Modify: `src/icewine_prediction/match_odds_sync_service.py`

- [ ] **Step 1: Set the single source of truth for trusted Pinnacle order**

Use `(oddspapi, pinnacle)`, `(the_odds_api, pinnacle)`, `(zqcf918, pinnacle)` for both Pinnacle and trusted selection constants. Remove SBOBet from trusted priority without deleting database rows.

- [ ] **Step 2: Make Oddspapi the default and run unresolved IDs through later providers**

Refactor the shared sync loop so the default Oddspapi run executes first, The Odds API executes only for IDs without trusted snapshots, and zqcf918 executes only for IDs still unresolved. Preserve existing result counters and per-match error reporting. Keep explicit provider enum calls supported.

- [ ] **Step 3: Remove the shared SBOBet fallback path**

Delete the call site and helper use that passes `bookmaker="sbobet"`; leave the Oddspapi runner's explicit bookmaker option intact for legacy/manual tooling.

- [ ] **Step 4: Run focused tests and then the full odds-source suite**

Run the focused command from Task 1, then:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_odds_provider_selection_service.py tests/test_match_odds_sync_service.py tests/test_oddspapi_sync_runner.py tests/test_the_odds_api_sync_runner.py -q
```

Expected: all tests pass.

### Task 3: Validate the remaining eight matches without persistence

**Files:**
- Modify: `src/icewine_prediction/oddspapi_sync_runner.py`
- Modify: `src/icewine_prediction/cli.py`
- Test: `tests/test_oddspapi_sync_runner.py`

- [ ] **Step 1: Add a dry-run option to the single-match Oddspapi fetch path**

Expose a `persist=False`/`--dry-run` path that still performs fixture, market, and historical-odds requests, reports match and market counts, and skips writes to `historical_odds_snapshots`, `historical_odds_raw_snapshots`, and source-match persistence.

- [ ] **Step 2: Add a failing dry-run test**

Use a fake client and a test session; assert the report contains successful market counts while both snapshot tables remain empty.

- [ ] **Step 3: Implement the minimal dry-run behavior and verify it**

Run the new focused test, then run dry-run for the remaining eight IDs with the same 2026 window and compare the returned market counts and fixture confidence against existing The Odds API rows.

### Task 4: Add aliases and document the rollout

**Files:**
- Modify: `config/external_aliases.yaml`
- Create: `docs/交接/20260826-odds-provider-order-rollout.md`

- [ ] **Step 1: Add only verified Argentina and Brazil aliases**

Record the two low-confidence team-name mappings observed in the seven-match test after confirming the canonical and Oddspapi names from the source-match rows.

- [ ] **Step 2: Document test evidence and final order**

Record the seven passing samples, the eight dry-run results, the 30-second delay assessment, and the final provider chain. Include the exact focused verification commands.

- [ ] **Step 3: Run the complete relevant test set and inspect the diff**

Run the full odds-source and historical selection tests, then `git diff --check` and `git status --short`. Do not stage unrelated user changes.

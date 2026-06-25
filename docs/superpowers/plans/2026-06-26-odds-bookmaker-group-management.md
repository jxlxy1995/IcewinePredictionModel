# Odds Bookmaker Group Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the selected odds bookmaker group on match details, allow confirmed clearing of an SBOBet group, and let manual Pinnacle entry rebuild the group.

**Architecture:** Keep the selected odds group as the existing trusted priority choice: The Odds API/Pinnacle, Oddspapi/Pinnacle, then Oddspapi/SBOBet. Extend match detail coverage with the selected bookmaker, add a small historical odds service operation that deletes only `oddspapi/sbobet` main-table snapshots for a match, expose it through the web API, and wire the frontend to show the bookmaker and clear SBOBet with a confirmation.

**Tech Stack:** Python, SQLAlchemy, FastAPI-style route handlers, pytest, TypeScript, React, Vitest.

---

### Task 1: Backend Coverage Metadata

**Files:**
- Modify: `src/icewine_prediction/match_list_workspace_service.py`
- Test: `tests/test_match_list_workspace_service.py`

- [ ] Add failing tests that match detail coverage reports `bookmaker="sbobet"` when only SBOBet snapshots are selected and `bookmaker="pinnacle"` when Pinnacle and SBOBet both exist.
- [ ] Implement `ExecutionTimepointCoverage.bookmaker` as the normalized selected bookmaker for the filtered trusted group, or `None` when no group is selected.
- [ ] Verify `pytest tests/test_match_list_workspace_service.py -q`.

### Task 2: Clear SBOBet Main Snapshots

**Files:**
- Modify: `src/icewine_prediction/historical_odds_service.py`
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_historical_odds_service.py`
- Test: `tests/test_web_console_api.py`

- [ ] Add failing service test proving clearing removes only `historical_odds_snapshots` rows with `source_name="oddspapi"` and `bookmaker="sbobet"` for the match, leaving Pinnacle and raw snapshots untouched.
- [ ] Add failing API test for `POST /api/matches/{match_id}/execution-timepoint-odds/clear-sbobet` returning deleted count.
- [ ] Implement `clear_sbobet_execution_timepoint_odds_group` and the API route.
- [ ] Verify targeted backend tests.

### Task 3: Frontend Display and Actions

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/matchListWorkspace.ts`
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/mockData.ts`
- Test: `web/src/matchListWorkspace.test.ts`
- Test: `web/src/apiClient.test.ts`

- [ ] Add failing workspace tests that coverage view includes bookmaker label and only allows manual plus buttons when bookmaker is not SBOBet.
- [ ] Add failing API client test for clear SBOBet endpoint.
- [ ] Implement type fields, client function, coverage view fields, and Dashboard button with `window.confirm`.
- [ ] Verify targeted frontend tests.

### Task 4: Documentation and Regression Verification

**Files:**
- Modify: `docs/交接/2026-06-26-odds-provider-league-coverage-handoff.md`

- [ ] Document that clearing SBOBet deletes main-table snapshots only, so raw snapshots may still contain SBOBet while `historical_odds_snapshots` has Pinnacle or no rows.
- [ ] Run backend and frontend targeted suites.
- [ ] Run `git diff --check`.

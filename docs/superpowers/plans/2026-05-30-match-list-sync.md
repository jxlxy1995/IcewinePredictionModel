# Match List And Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Web `比赛列表` page that can sync recent fixtures/results and odds, browse local matches with filters, and open a dedicated match detail view.

**Architecture:** Add a backend match-list workspace service with `data_sync_runs` freshness records and sync action wrappers around existing sync runner functions. Expose workspace, sync, and match-detail endpoints, then add typed frontend helpers/components and a dashboard view where the list is the primary content.

**Tech Stack:** Python, SQLAlchemy, FastAPI, pytest, React, TypeScript, Vitest.

---

## File Structure

- Modify `src/icewine_prediction/models.py`: add `DataSyncRun`.
- Create `src/icewine_prediction/match_list_workspace_service.py`: filters, freshness, odds summaries, sync run recording, detail payload logic.
- Modify `src/icewine_prediction/web_api.py`: expose match-list workspace, sync, and detail endpoints.
- Create `tests/test_match_list_workspace_service.py`: backend service tests.
- Modify `tests/test_web_console_api.py`: API endpoint tests.
- Modify `web/src/types.ts`: add match list workspace/detail types.
- Modify `web/src/apiClient.ts`: add match list API calls.
- Create `web/src/matchListWorkspace.ts`: frontend format/filter helpers.
- Create `web/src/matchListWorkspace.test.ts`: frontend helper tests.
- Create `web/src/components/MatchListTable.tsx`: match list table.
- Modify `web/src/mockData.ts`: add mock match list workspace/detail.
- Modify `web/src/pages/DashboardPage.tsx`: add `比赛列表` view and match detail state.
- Modify `web/src/styles.css`: compact sync toolbar/list styling if needed.

## Task 1: Backend Workspace Service

**Files:**
- Modify: `src/icewine_prediction/models.py`
- Create: `src/icewine_prediction/match_list_workspace_service.py`
- Test: `tests/test_match_list_workspace_service.py`

- [ ] Write failing tests for `DataSyncRun`, default next-24h window, league/status/odds/search filters, freshness metadata, odds summary, and match detail placeholders.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_list_workspace_service.py -q` and confirm missing service/model failures.
- [ ] Add `DataSyncRun` model.
- [ ] Implement workspace dataclasses and functions:
  - `build_match_list_workspace`
  - `build_match_detail`
  - `record_sync_run`
  - `build_latest_sync_metadata`
- [ ] Run focused service tests and confirm they pass.

## Task 2: Backend API

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] Write failing API tests for:
  - `GET /api/match-list/workspace`
  - `POST /api/match-list/sync/fixtures-results`
  - `POST /api/match-list/sync/odds`
  - `GET /api/matches/{match_id}/detail`
- [ ] Run focused API tests and confirm missing endpoint failures.
- [ ] Add endpoint handlers and payload builders.
- [ ] Use injectable sync runners in `create_web_app` so tests avoid real provider calls.
- [ ] Run `pytest tests/test_match_list_workspace_service.py tests/test_web_console_api.py -q`.

## Task 3: Frontend Types And Helpers

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Create: `web/src/matchListWorkspace.ts`
- Create: `web/src/matchListWorkspace.test.ts`
- Modify: `web/src/mockData.ts`

- [ ] Write failing Vitest tests for freshness cards, default filter labels, match row labels, status labels, odds labels, and detail placeholders.
- [ ] Run `npm test -- matchListWorkspace.test.ts` from `web` and confirm missing helper failures.
- [ ] Add types, API client calls, mock data, and helper functions.
- [ ] Run focused Vitest tests and confirm they pass.

## Task 4: Frontend Page

**Files:**
- Create: `web/src/components/MatchListTable.tsx`
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/styles.css`

- [ ] Add `比赛列表` nav item.
- [ ] Add compact freshness/sync toolbar.
- [ ] Add filters and list table with default next-24h workspace data.
- [ ] Add detail view state that opens a dedicated detail screen inside the dashboard when a row is clicked.
- [ ] Wire sync buttons to API calls and refresh workspace.
- [ ] Run `npm test -- matchListWorkspace.test.ts`.
- [ ] Run `npm run build`.

## Task 5: Verification

**Files:**
- Review all touched backend/frontend files.

- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_list_workspace_service.py tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py -q`.
- [ ] Run `npm test -- matchListWorkspace.test.ts paperRecommendationWorkspace.test.ts` from `web`.
- [ ] Run `npm run build` from `web`.
- [ ] Start API/frontend dev servers and provide URL.

## Self-Review

- Spec coverage: plan covers independent `比赛列表`, compact sync toolbar, latest sync run freshness, default next 24h, filters, all-match browsing through presets, match detail page, odds summaries, and recommendation placeholders.
- Placeholder scan: the only placeholder concept is the requested future recommendation/team-data placeholder; no implementation TBDs.
- Type consistency: backend uses `DataSyncRun`; frontend uses `MatchListWorkspace` and `MatchDetail`.

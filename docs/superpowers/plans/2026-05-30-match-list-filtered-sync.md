# Match List Filtered Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make match-list sync buttons operate on the active filtered match set, add row-level sync actions, and show expandable success/failure/skipped details.

**Architecture:** Add a small backend sync-report layer around existing match filtering, API-Football fixture refresh, and OddsPapi `match_ids` backfill. The frontend calls the same filtered payload used by the list, stores the latest report, and renders grouped details.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TypeScript, Vitest.

---

### Task 1: Backend Filtered Target Selection

**Files:**
- Modify: `src/icewine_prediction/match_list_workspace_service.py`
- Test: `tests/test_match_list_workspace_service.py`

- [ ] Add tests for selecting all match ids from the full filter set without applying the visible list limit.
- [ ] Implement `select_match_list_sync_targets(...)` by reusing the existing match-list query semantics.
- [ ] Run `pytest tests/test_match_list_workspace_service.py -q`.

### Task 2: Backend Sync Reports And Routes

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] Add tests for bulk routes passing filtered match ids into injected syncers and returning grouped report payloads.
- [ ] Add tests for single-match routes passing exactly one match id.
- [ ] Implement report payload builders and route payload parsing.
- [ ] Keep `DataSyncRun` recording and cache invalidation.
- [ ] Run `pytest tests/test_web_console_api.py -q`.

### Task 3: Real Sync Adapters

**Files:**
- Modify: `src/icewine_prediction/web_api.py`

- [ ] Implement fixtures/results adapter using API-Football fixture ids for selected matches.
- [ ] Implement odds adapter using OddsPapi batch backfill with `match_ids`.
- [ ] Keep injected syncer tests fast by allowing callable overrides.

### Task 4: Frontend API And Helpers

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/matchListWorkspace.ts`
- Test: `web/src/apiClient.test.ts`
- Test: `web/src/matchListWorkspace.test.ts`

- [ ] Add sync report types.
- [ ] Send full filter payload for bulk sync routes.
- [ ] Add single-match sync client functions.
- [ ] Add helper functions for compact result labels.
- [ ] Run `npm test -- apiClient.test.ts matchListWorkspace.test.ts`.

### Task 5: Frontend UI

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/components/MatchListTable.tsx`
- Modify: `web/src/styles.css`

- [ ] Remove day-count inputs from the sync strip.
- [ ] Render a sync result details panel with success/failed/skipped `<details>` groups.
- [ ] Add row-level `赛果` and `赔率` buttons that stop row navigation.
- [ ] Refresh match-list data after every sync.

### Task 6: Verification

**Files:**
- No new files.

- [ ] Run `pytest tests/test_match_list_workspace_service.py tests/test_web_console_api.py -q`.
- [ ] Run `cd web; npm test -- apiClient.test.ts matchListWorkspace.test.ts`.
- [ ] Run `cd web; npm run build`.
- [ ] Restart the local web app if backend changed.

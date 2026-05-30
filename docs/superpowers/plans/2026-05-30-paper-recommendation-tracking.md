# Paper Recommendation Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a semi-automatic paper recommendation tracking loop with a dedicated Web console page, independent records, manual edits, and post-match settlement.

**Architecture:** Add a dedicated `PaperRecommendationRecord` ORM model and a focused service module that converts valid queue candidates into records, edits records, settles records, and builds workspace summaries. Expose the service through FastAPI endpoints, then add typed frontend workspace helpers, mock data, and a `纸面跟踪` view in the existing dashboard.

**Tech Stack:** Python, SQLAlchemy, FastAPI, pytest, React, TypeScript, Vitest.

---

## File Structure

- Modify `src/icewine_prediction/models.py`: add `PaperRecommendationRecord`.
- Modify `src/icewine_prediction/database.py`: add SQLite schema backfill for paper record columns/indexes if needed.
- Create `src/icewine_prediction/paper_recommendation_tracking_service.py`: paper strategy metadata, create/edit/void/settle/workspace summary logic.
- Modify `src/icewine_prediction/web_api.py`: add paper tracking endpoints and payload builders.
- Create `tests/test_paper_recommendation_tracking_service.py`: service behavior tests.
- Modify `tests/test_web_console_api.py`: endpoint tests for workspace/create/edit/settle/void.
- Modify `web/src/types.ts`: add paper tracking payload types.
- Modify `web/src/apiClient.ts`: load workspace and call paper tracking actions.
- Create `web/src/paperRecommendationWorkspace.ts`: frontend summary/grouping/format helpers.
- Create `web/src/paperRecommendationWorkspace.test.ts`: frontend helper tests.
- Create `web/src/components/PaperRecommendationTables.tsx`: candidate and record tables with edit controls.
- Modify `web/src/mockData.ts`: add mock paper workspace.
- Modify `web/src/pages/DashboardPage.tsx`: add `纸面跟踪` nav and view.

## Task 1: Backend Model And Service

**Files:**
- Modify: `src/icewine_prediction/models.py`
- Create: `src/icewine_prediction/paper_recommendation_tracking_service.py`
- Test: `tests/test_paper_recommendation_tracking_service.py`

- [ ] Write failing service tests for creating a record from a valid queue candidate, rejecting invalid candidates, duplicate active records, editing pending records, voiding records, settling Asian handicap records, and building grouped summaries.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_tracking_service.py -q` and confirm failures are due to missing model/service.
- [ ] Add `PaperRecommendationRecord` with paper strategy, original/current line and odds, manual adjustment, status, and settlement fields.
- [ ] Implement strategy metadata constants:
  - `ASIAN_AWAY_COVER_HGB_EDGE_V1_KEY = "asian_away_cover_hgb_edge_v1"`
  - Display name `亚盘客队方向 · HGB边际 v1`
- [ ] Implement `create_paper_record_from_queue_row`, `edit_paper_record`, `void_paper_record`, `settle_paper_records`, and `build_paper_tracking_workspace`.
- [ ] Run the focused service tests and confirm they pass.
- [ ] Commit backend model/service tests and implementation.

## Task 2: Web API

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] Write failing API tests for:
  - `GET /api/paper-recommendations/workspace`
  - `POST /api/paper-recommendations/records`
  - `PATCH /api/paper-recommendations/records/{id}`
  - `POST /api/paper-recommendations/settle`
  - `POST /api/paper-recommendations/records/{id}/void`
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q` and confirm the new tests fail for missing endpoints.
- [ ] Add routes that call the tracking service.
- [ ] Ensure payloads include Beijing-time timestamps, Chinese display names, strategy display name/key, and `recommended_handicap`.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py -q`.
- [ ] Commit API tests and implementation.

## Task 3: Frontend Types And Workspace Helpers

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Create: `web/src/paperRecommendationWorkspace.ts`
- Create: `web/src/paperRecommendationWorkspace.test.ts`
- Modify: `web/src/mockData.ts`

- [ ] Write failing Vitest tests for summary cards, record grouping, settlement labels, and candidate recordability.
- [ ] Run `npm test -- paperRecommendationWorkspace.test.ts` from `web` and confirm failure because helpers/types do not exist.
- [ ] Add TypeScript types for paper candidates, records, summary groups, strategies, and workspace.
- [ ] Add API client functions for loading workspace and posting record/edit/settle/void actions.
- [ ] Add mock workspace data matching the API shape.
- [ ] Implement helper functions for summary cards, grouping, recordability, and labels.
- [ ] Run `npm test -- paperRecommendationWorkspace.test.ts`.
- [ ] Commit frontend helper tests and implementation.

## Task 4: Frontend Page

**Files:**
- Create: `web/src/components/PaperRecommendationTables.tsx`
- Modify: `web/src/pages/DashboardPage.tsx`
- Test: `web/src/paperRecommendationWorkspace.test.ts`

- [ ] Add table components for candidates and records, including buttons for record/edit/void.
- [ ] Add `纸面跟踪` to the sidebar and a `PaperTrackingView`.
- [ ] Wire refresh, record, batch record, settle, edit, and void actions to the API client.
- [ ] Keep labels compact and operational: Chinese strategy name first, English key secondary.
- [ ] Run `npm test -- paperRecommendationWorkspace.test.ts`.
- [ ] Run `npm run build`.
- [ ] Commit frontend page implementation.

## Task 5: Final Verification

**Files:**
- Review touched backend/frontend files.

- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_tracking_service.py tests/test_web_console_api.py -q`.
- [ ] Run `npm test -- paperRecommendationWorkspace.test.ts` from `web`.
- [ ] Run `npm run build` from `web`.
- [ ] Run `git status --short` and confirm only intended files changed.
- [ ] Start the dev server and provide the local URL.

## Self-Review

- Spec coverage: the plan covers the independent table, semi-automatic recording, strategy Chinese display name/key, record-time lock, manual edit, void, settlement, workspace API, Web page, summaries, and tests.
- Placeholder scan: no TBD/TODO/fill-in placeholders.
- Type consistency: backend uses `PaperRecommendationRecord`; frontend uses paper workspace terminology matching API payloads.

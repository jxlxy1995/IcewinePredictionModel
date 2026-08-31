# Multi-Source Execution Timepoint Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use 18-cell standard-timepoint coverage to drive Oddspapi -> The Odds API -> zqcf918 fallback while exposing the selected source and source-specific colors in the web matrix.

**Architecture:** Keep provider persistence independent. Extract/reuse a backend coverage evaluator for the 18 standard cells, use it as the fallback gate after each provider, and return the selected source per cell. The frontend maps stable source names to centralized semantic color classes while retaining accessible text/tooltips.

**Tech Stack:** Python, SQLAlchemy, pytest, TypeScript, React, Vitest, CSS.

**Spec:** `docs/设计/20260901-多源标准时点赔率补齐与矩阵来源标识设计.md`

## Global Constraints

- Oddspapi remains first priority and uses a 6-minute strict tolerance for Pinnacle.
- The Odds API request behavior remains unchanged.
- Each provider writes only its own `source_name`; cross-provider selection happens only during coverage evaluation/readout.
- Missing cells are never synthesized by interpolation or copying.
- Existing manual supplement and SBOBet behavior must remain compatible.
- Automatic fallback completion is based on core Asian Handicap + Total Goals coverage (12/12); the full 18-cell count remains a separate quality metric.

---

### Task 1: Add source-specific Oddspapi tolerance

**Files:**
- Modify: `src/icewine_prediction/execution_timepoint_service.py`
- Test: `tests/test_execution_timepoint_service.py`

**Interfaces:**
- Preserve `select_execution_timepoint_pair(...)` signature.
- Add `("oddspapi", "pinnacle"): 6` to the existing source/bookmaker policy.

- [ ] Add a failing boundary test for an Oddspapi pair at `5:00.1` after target and assert it is selected.
- [ ] Add a failing boundary test at exactly/over six minutes and assert it is not selected.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_execution_timepoint_service.py -q` and confirm the new tests fail before implementation.
- [ ] Implement only the policy-map change, retaining the strict `< tolerance` comparison.
- [ ] Run the focused test file and the existing source-policy tests; expect all pass.

### Task 2: Introduce reusable 18-cell coverage evaluation

**Files:**
- Create: `src/icewine_prediction/execution_timepoint_coverage_service.py`
- Modify: `src/icewine_prediction/match_list_workspace_service.py`
- Test: `tests/test_execution_timepoint_coverage_service.py`

**Interfaces:**
- Produce `evaluate_standard_execution_timepoint_coverage(snapshots, kickoff_time) -> StandardExecutionTimepointCoverage`.
- The result exposes full `available_count`/`total_count`, core `core_available_count`/`core_total_count`/`core_complete`, full/core missing cells, and selected cells with `source_name`, `snapshot_time`, and `market_line`.
- Use existing `TRUSTED_SNAPSHOT_PRIORITY`, `_pair_market_snapshots`, and `select_execution_timepoint_pair` semantics.

- [ ] Write tests for 18/18, a 15/18 result, and per-cell priority where Oddspapi supplies one cell and The Odds API supplies another.
- [ ] Run the new focused tests and confirm failure because the evaluator does not exist.
- [ ] Implement the evaluator without querying or mutating the database.
- [ ] Refactor the existing detail coverage builder to consume the evaluator, preserving current health labels and counts.
- [ ] Run coverage, workspace, and web API backend tests; expect unchanged JSON fields plus the new source fields once added in Task 4.

### Task 3: Gate provider fallback by 18/18 coverage

**Files:**
- Modify: `src/icewine_prediction/match_odds_sync_service.py`
- Test: `tests/test_match_odds_sync_service.py`

**Interfaces:**
- Replace the Oddspapi fallback gate's “any trusted snapshot” check with a database-backed `has_complete_core_execution_timepoint_coverage(session, match_id)` helper; retain full coverage for quality reporting.
- Keep `has_trusted_historical_odds` for existing list/status behavior unless a test proves that behavior must change.

- [ ] Add tests where Oddspapi writes partial standard coverage and assert The Odds API is invoked with only those match IDs.
- [ ] Add tests where Oddspapi reaches 18/18 and assert neither fallback provider is invoked.
- [ ] Add tests where The Odds API leaves a gap and assert zqcf918 is invoked only after the second coverage check.
- [ ] Run the focused sync-service tests and confirm failure against the old any-snapshot gate.
- [ ] Implement the coverage checks after each provider transaction, preserving rollback and existing result accounting.
- [ ] Add structured progress/log fields for before/after coverage and missing cell identifiers.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_odds_sync_service.py -q`.

### Task 4: Return selected source in backend matrix payloads

**Files:**
- Modify: `src/icewine_prediction/match_list_workspace_service.py`
- Modify: `src/icewine_prediction/web_api.py` only if serialization needs explicit handling
- Test: `tests/test_web_console_api.py`

**Interfaces:**
- Add `source_name: str | None` to `ExecutionTimepointCoverageCell`.
- Add `source_name: str | None` to each odds-table market payload (`asian_handicap`, `total_goals`, `match_winner`).
- Populate the value from the actual selected pair; missing values remain `null`.

- [ ] Add API tests with mixed sources and assert each cell reports the source selected by priority.
- [ ] Add API tests for missing cells and assert `source_name` is `null`.
- [ ] Implement dataclass and formatter changes without changing the existing source priority.
- [ ] Run `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q` and the related workspace tests.

### Task 5: Add centralized frontend source styling and accessibility

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/matchListWorkspace.ts`
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/styles.css`
- Test: `web/src/matchListWorkspace.test.ts`

**Interfaces:**
- Extend frontend coverage and odds-table types with `source_name: string | null`.
- Map source names to semantic classes: `source-oddspapi`, `source-the-odds-api`, `source-zqcf918`, and `source-missing`.
- Keep `available`/`missing` state separate from source styling.

- [ ] Add view-model tests for all three known sources, unknown source fallback, and missing cell.
- [ ] Add view-model tests asserting the title includes source label for available cells.
- [ ] Implement a single source metadata map containing label, CSS class, and accessible label.
- [ ] Apply source class to coverage cells and add a compact legend using the same metadata map.
- [ ] Add source labels/tooltips to odds-table cells where a source is present; do not rely on color alone.
- [ ] Define the four CSS classes with fixed dimensions and the agreed blue/amber/red/neutral palette; preserve responsive horizontal scrolling.
- [ ] Run `npm test` from `web` and then `npm run build` from `web`; expect Vitest to pass and `tsc`/Vite to complete successfully.

### Task 6: Full verification and documentation handoff

**Files:**
- Verify: all files above
- Test: `tests/test_execution_timepoint_service.py`, `tests/test_execution_timepoint_coverage_service.py`, `tests/test_match_odds_sync_service.py`, `tests/test_web_console_api.py`, `web/src/matchListWorkspace.test.ts`

- [ ] Run focused Python tests with `C:\ProgramData\anaconda3\python.exe` and `PYTHONPATH=src`.
- [ ] Run the full backend test suite if the focused tests pass.
- [ ] Run `npm test` and `npm run build` from `web`.
- [ ] Manually inspect a mixed-source match detail response and verify 18/18, source names, titles, and colors.
- [ ] Record any residual gaps, especially provider-specific league coverage, in the implementation handoff.

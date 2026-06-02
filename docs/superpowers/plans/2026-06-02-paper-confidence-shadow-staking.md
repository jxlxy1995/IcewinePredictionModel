# Paper Confidence Shadow Staking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a paper-only same-direction confidence and dynamic stake simulation layer while preserving existing per-strategy paper ROI reporting.

**Architecture:** Add a focused backend service that derives same-direction simulation groups from raw `PaperRecommendationRecord` rows on demand. Expose the derived groups through the existing paper workspace API, then add frontend display helpers and a dedicated simulation section in the paper tracking page. No DB migration is required for the first version.

**Tech Stack:** Python 3, SQLAlchemy ORM models, pytest, FastAPI payload builders, TypeScript, React, Vitest.

---

### Task 1: Backend Same-Direction Simulation Service

**Files:**
- Create: `src/icewine_prediction/paper_confidence_service.py`
- Test: `tests/test_paper_confidence_service.py`

- [ ] **Step 1: Write failing service tests**

Add tests that seed paper records using existing helpers from `tests/test_paper_recommendation_tracking_service.py`, then assert:

```python
def test_build_paper_confidence_workspace_groups_same_direction_strategy_records(session):
    match = _seed_match(session, home_score=1, away_score=1, status="finished")
    create_paper_record_from_queue_row(session, _queue_row(match, status="candidate", line=Decimal("-0.50")), recorded_at=_now())
    create_paper_record_from_queue_row(
        session,
        _queue_row(
            match,
            status="candidate",
            line=Decimal("-0.50"),
            edge=Decimal("0.2200"),
            strategy_key="asian_away_cover_hgb_bucket_v2",
            strategy_display_name="亚盘客队方向 · HGB分盘口桶 v2",
            signal_version="v2",
            risk_tags=("line_bucket:away_underdog", "strategy:bucket_v2"),
        ),
        recorded_at=_now(),
    )
    settle_paper_records(session, settled_at=_now())

    workspace = build_paper_confidence_workspace(session.query(PaperRecommendationRecord).all())

    assert workspace.summary.group_count == 1
    group = workspace.groups[0]
    assert group.match_id == match.id
    assert group.market_type == "asian_handicap"
    assert group.logical_side == "away_cover"
    assert group.triggered_strategy_keys == (
        "asian_away_cover_hgb_edge_v1",
        "asian_away_cover_hgb_bucket_v2",
    )
    assert group.signal_families == ("asian_away_hgb",)
    assert group.flat_profit_units == Decimal("0.930")
    assert group.weighted_profit_units == group.suggested_stake_units * group.flat_profit_units
```

Also add tests for separate side/market grouping, stake mapping caps, representative selection preferring bucket + higher edge, and weighted ROI not summing duplicate strategy records.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_confidence_service.py -q
```

Expected: FAIL because `icewine_prediction.paper_confidence_service` does not exist.

- [ ] **Step 3: Implement service**

Create dataclasses:

```python
PaperConfidenceGroup
PaperConfidenceGroupSummary
PaperConfidenceSummary
PaperConfidenceWorkspace
```

Implement:

```python
build_paper_confidence_workspace(records: list[PaperRecommendationRecord]) -> PaperConfidenceWorkspace
strategy_family(strategy_key: str) -> str
confidence_score_for_group(records: list[PaperRecommendationRecord], representative: PaperRecommendationRecord) -> tuple[int, Decimal, str]
stake_for_score(score: int) -> Decimal
```

Use `match_id + market_type + side` as the grouping key, exclude voided records unless all records in the group are voided, choose representative by non-void status, complete line/odds, bucket strategy priority, edge, model probability margin, created time, id. Compute flat profit from the representative record only.

- [ ] **Step 4: Run backend service tests**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_confidence_service.py -q
```

Expected: PASS.

### Task 2: API Payload Integration

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] **Step 1: Write failing API test**

Add or extend a paper workspace test so the response includes:

```python
simulation = payload["confidence_simulation"]
assert simulation["summary"]["group_count"] == 1
assert simulation["groups"][0]["triggered_strategy_keys"] == [
    "asian_away_cover_hgb_edge_v1",
    "asian_away_cover_hgb_bucket_v2",
]
assert simulation["groups"][0]["suggested_stake_units"] in {"1.00", "1.25"}
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_records_v2_paper_candidate_by_strategy_key -q
```

Expected: FAIL because `confidence_simulation` is absent.

- [ ] **Step 3: Add payload builder**

Import `build_paper_confidence_workspace` in `web_api.py`. In `build_paper_recommendation_workspace_payload`, add:

```python
"confidence_simulation": build_paper_confidence_workspace_payload(
    build_paper_confidence_workspace(workspace.records)
)
```

Create `build_paper_confidence_workspace_payload` and helper payload builders that format decimals as strings.

- [ ] **Step 4: Run API test**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py::test_web_console_api_records_v2_paper_candidate_by_strategy_key -q
```

Expected: PASS.

### Task 3: Frontend Types And Workspace Helpers

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/paperRecommendationWorkspace.ts`
- Test: `web/src/paperRecommendationWorkspace.test.ts`

- [ ] **Step 1: Write failing frontend helper test**

Add `confidence_simulation` to the test workspace and assert:

```typescript
expect(buildPaperConfidenceSimulationRows(workspace)[0]).toMatchObject({
  confidenceScore: "72",
  suggestedStakeUnits: "1.25",
  triggeredSignals: "asian_away_cover_hgb_edge_v1, asian_away_cover_hgb_bucket_v2",
  weightedProfitUnits: "1.163"
});
```

Also assert summary cards include weighted ROI.

- [ ] **Step 2: Run frontend helper test to verify failure**

Run:

```powershell
cd web; npm test -- paperRecommendationWorkspace.test.ts --runInBand
```

Expected: FAIL because helper functions and types do not exist.

- [ ] **Step 3: Add types and helper functions**

Add `PaperConfidenceSimulationGroup`, `PaperConfidenceSimulationSummary`, and `PaperConfidenceSimulationWorkspace` to `types.ts`, and add `confidence_simulation` to `PaperRecommendationWorkspace`.

Add helper functions:

```typescript
buildPaperConfidenceSimulationCards(workspace)
buildPaperConfidenceSimulationRows(workspace)
```

- [ ] **Step 4: Run frontend helper test**

Run:

```powershell
cd web; npm test -- paperRecommendationWorkspace.test.ts --runInBand
```

Expected: PASS.

### Task 4: Frontend Simulation Section

**Files:**
- Modify: `web/src/components/PaperRecommendationTables.tsx`
- Modify: `web/src/pages/DashboardPage.tsx`
- Test: `web/src/paperRecommendationWorkspace.test.ts`

- [ ] **Step 1: Add component tests through helper coverage**

Use the helper tests from Task 3 as the behavioral guard for display-ready rows and cards.

- [ ] **Step 2: Implement simulation table component**

Add `PaperConfidenceSimulationTable` to `PaperRecommendationTables.tsx`. It should render group rows with fixture, recommendation, confidence score, suggested stake, cap reason, triggered signals, flat profit, weighted profit, and status.

- [ ] **Step 3: Wire section into PaperTrackingView**

Import `PaperConfidenceSimulationTable` and helper cards. Add a dedicated panel titled for same-direction simulation below strategy records and above group summary panels.

- [ ] **Step 4: Run frontend tests**

Run:

```powershell
cd web; npm test -- paperRecommendationWorkspace.test.ts --runInBand
```

Expected: PASS.

### Task 5: Focused Verification

**Files:**
- No new files

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_confidence_service.py tests/test_paper_recommendation_tracking_service.py tests/test_web_console_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests**

Run:

```powershell
cd web; npm test -- paperRecommendationWorkspace.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 3: Commit**

Run:

```powershell
git add src/icewine_prediction/paper_confidence_service.py src/icewine_prediction/web_api.py tests/test_paper_confidence_service.py tests/test_web_console_api.py web/src/types.ts web/src/paperRecommendationWorkspace.ts web/src/components/PaperRecommendationTables.tsx web/src/pages/DashboardPage.tsx web/src/paperRecommendationWorkspace.test.ts docs/superpowers/plans/2026-06-02-paper-confidence-shadow-staking.md
git commit -m "Add paper confidence shadow staking"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: plan covers derived backend grouping/scoring, API payload, web simulation section, flat strategy view preservation, and focused tests. It intentionally does not implement persistence because the approved first version allows on-demand derived computation.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: backend uses `confidence_simulation`; frontend mirrors the same payload name.

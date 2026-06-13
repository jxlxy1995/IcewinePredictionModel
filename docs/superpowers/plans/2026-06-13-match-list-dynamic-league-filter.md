# Match List Dynamic League Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make match-list league choices depend on the active time range and reset the selected league when the time range changes.

**Architecture:** Backend computes league options from distinct matches inside the current time window. Frontend uses a small filter-update helper so start/end time changes always clear `league_name`.

**Tech Stack:** Python, SQLAlchemy, pytest, React, TypeScript, Vitest.

---

### Task 1: Backend Dynamic League Options

**Files:**
- Modify: `tests/test_match_list_workspace_service.py`
- Modify: `src/icewine_prediction/match_list_workspace_service.py`

- [ ] **Step 1: Write the failing test**

Add this test near the other match-list workspace filter tests:

```python
def test_match_list_workspace_league_options_follow_time_window(session):
    now = datetime(2026, 5, 30, 10, 0, tzinfo=BEIJING)
    inside_league = League(name="J1 League", country_or_region="Japan", level=1)
    outside_league = League(name="K League 1", country_or_region="Korea", level=1)
    session.add_all([inside_league, outside_league])
    session.flush()
    _add_match(session, inside_league, "Inside League", datetime(2026, 5, 30, 13, 0, tzinfo=BEIJING))
    _add_match(session, outside_league, "Outside League", datetime(2026, 6, 2, 13, 0, tzinfo=BEIJING))
    session.commit()

    workspace = build_match_list_workspace(
        session,
        now=now,
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=BEIJING),
        end_time=datetime(2026, 5, 31, 0, 0, tzinfo=BEIJING),
    )

    assert [league.name for league in workspace.leagues] == ["J1 League"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests\test_match_list_workspace_service.py::test_match_list_workspace_league_options_follow_time_window -q
```

Expected: FAIL because `_league_options()` still includes `"K League 1"`.

- [ ] **Step 3: Implement minimal backend change**

Change `_league_options()` to accept `start` and `end`, query only matches in that window, and pass those arguments from `build_match_list_workspace()`.

- [ ] **Step 4: Run backend focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests\test_match_list_workspace_service.py -q
```

Expected: PASS.

### Task 2: Frontend Time Changes Clear League

**Files:**
- Modify: `web/src/matchListWorkspace.ts`
- Modify: `web/src/matchListWorkspace.test.ts`
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Write the failing test**

Add a helper test:

```typescript
it("clears league selection when a time filter changes", () => {
  expect(buildMatchTimeFilterChange("start_time", "2026-06-01T00:00")).toEqual({
    league_name: "",
    start_time: "2026-06-01T00:00"
  });
  expect(buildMatchTimeFilterChange("end_time", "2026-06-02T12:00")).toEqual({
    end_time: "2026-06-02T12:00",
    league_name: ""
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
Push-Location web; npm test -- matchListWorkspace.test.ts; Pop-Location
```

Expected: FAIL because `buildMatchTimeFilterChange` is not exported yet.

- [ ] **Step 3: Implement frontend helper and wire inputs**

Export `buildMatchTimeFilterChange()` from `web/src/matchListWorkspace.ts` and import it in `DashboardPage.tsx`. Use it in both `start_time` and `end_time` input `onChange` handlers in `FilteredMatchListView`.

- [ ] **Step 4: Run frontend focused tests**

Run:

```powershell
Push-Location web; npm test -- matchListWorkspace.test.ts; Pop-Location
```

Expected: PASS.

### Task 3: Final Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused backend and frontend checks**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; C:\ProgramData\anaconda3\python.exe -m pytest tests\test_match_list_workspace_service.py -q
Push-Location web; npm test -- matchListWorkspace.test.ts; Pop-Location
```

Expected: both commands PASS.

- [ ] **Step 2: Review diff**

Run:

```powershell
git diff -- src\icewine_prediction\match_list_workspace_service.py tests\test_match_list_workspace_service.py web\src\matchListWorkspace.ts web\src\matchListWorkspace.test.ts web\src\pages\DashboardPage.tsx docs\superpowers\specs\2026-06-13-match-list-dynamic-league-filter-design.md docs\superpowers\plans\2026-06-13-match-list-dynamic-league-filter.md
```

Expected: diff only covers the dynamic league-filter behavior and its tests/docs.

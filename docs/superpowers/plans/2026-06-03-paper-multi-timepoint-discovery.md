# Paper Multi-Timepoint Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scheduled paper queue and finished historical backfill use the same multi-timepoint discovery and robustness-filtered candidate retention logic.

**Architecture:** Add a focused multi-timepoint discovery helper around the existing paper queue row/scoring primitives, then make `build_paper_recommendation_queue` consume it when oddspapi historical snapshots are available. Keep live snapshot fallback unchanged. Add a compact match-level discard count to the queue report and diagnostics payload.

**Tech Stack:** Python 3, SQLAlchemy ORM, pytest, existing `paper_recommendation_queue_service.py` scorer/row helpers, existing `execution_robustness_rules.py`.

---

## File Structure

- Modify `src/icewine_prediction/execution_robustness_rules.py`: change `total_goals_hgb_confirmed_under_mid_275_v1` from observe mode to normal filter mode.
- Modify `src/icewine_prediction/paper_recommendation_queue_service.py`: add multi-timepoint discovery data structures and use them in `_build_queue_rows`; add `discarded_by_robustness_match_count` to `PaperRecommendationQueueReport`.
- Modify `src/icewine_prediction/web_api.py`: expose the discard count in queue payload and diagnostics payload.
- Modify `tests/test_paper_recommendation_queue_service.py`: cover union discovery, scheduled/finished parity, confirmed-under filter mode, simple discard count, and scorer call count.
- Modify `tests/test_web_console_api.py`: cover the new diagnostics field in API payloads.
- Modify `web/src/types.ts` only if TypeScript tests require the new field to be typed; the UI can keep rendering existing status cards in the first version.

---

### Task 1: Lock In Rule And Queue Behavior With Failing Tests

**Files:**
- Modify: `tests/test_paper_recommendation_queue_service.py`
- Test: `tests/test_paper_recommendation_queue_service.py`

- [ ] **Step 1: Add a test proving confirmed-under is no longer observe mode**

Add this import near the existing queue service imports:

```python
from icewine_prediction.execution_robustness_rules import DEFAULT_SELECTED_ROBUSTNESS_RULES
```

Add this test near the robustness tests:

```python
def test_confirmed_under_mid_275_uses_filter_mode():
    rule = DEFAULT_SELECTED_ROBUSTNESS_RULES["total_goals_hgb_confirmed_under_mid_275_v1"]

    assert rule.mode == "filter"
```

- [ ] **Step 2: Add a test for latest-only discovery plus fixed-target robustness**

Add this test near `test_build_paper_recommendation_queue_uses_historical_odds_for_scheduled_match`:

```python
def test_build_paper_recommendation_queue_discovers_latest_only_candidate_when_fixed_targets_are_robust(session):
    league = League(name="Latest Union League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Latest Home")
    away = Team(canonical_name="Latest Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="scheduled",
        source_name="api_football",
        source_match_id="scheduled-latest-union",
    )
    session.add(match)
    session.flush()
    for target_minutes in (25, 20, 15, 10, 5):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    _add_historical_market_pair_at_target(
        session,
        match,
        target_minutes=1,
        market_type="asian_handicap",
        line=Decimal("-0.50"),
        outcomes={"home": Decimal("2.05"), "away": Decimal("1.80")},
    )
    session.commit()
    scorer_calls = []

    def fake_scorer(row):
        scorer_calls.append(row["asian_handicap_away_odds"])
        edge = Decimal("0.1300") if row["asian_handicap_away_odds"] == "1.800" else Decimal("0.0900")
        return PaperQueueScore(
            side="away_cover",
            model_probability=(Decimal(row["asian_handicap_away_implied_probability"]) + edge).quantize(Decimal("0.0001")),
            market_probability=Decimal(row["asian_handicap_away_implied_probability"]),
            edge=edge,
            model_name="fake_hgb",
        )

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 30, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        hours=2,
        scorer=fake_scorer,
    )

    assert report.candidate_count == 1
    candidate = report.rows[0]
    assert candidate.status == "candidate"
    assert candidate.execution_target == "T-15"
    assert candidate.robustness_status == "kept"
    assert candidate.robustness_seen_count == 5
    assert candidate.robustness_observed_targets == (5, 10, 15, 20, 25)
    assert report.discarded_by_robustness_match_count == 0
    assert len(scorer_calls) <= 6
```

- [ ] **Step 3: Add a test that finished and scheduled discard the same fragile match**

Replace `test_build_paper_recommendation_queue_marks_finished_candidate_robustness_without_filtering` with:

```python
def test_build_paper_recommendation_queue_filters_finished_candidate_like_scheduled(session):
    league = League(name="Finished Fragile League", country_or_region="Norway", level=1, is_enabled=True)
    home = Team(canonical_name="Finished Fragile Home")
    away = Team(canonical_name="Finished Fragile Away")
    session.add_all([league, home, away])
    session.flush()
    kickoff = datetime(2026, 5, 30, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    match = Match(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        status="finished",
        home_score=1,
        away_score=2,
        source_name="api_football",
        source_match_id="finished-fragile",
    )
    session.add(match)
    session.flush()
    for target_minutes in (15, 5):
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="asian_handicap",
            line=Decimal("-0.50"),
            outcomes={"home": Decimal("1.99"), "away": Decimal("1.93")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="total_goals",
            line=Decimal("2.50"),
            outcomes={"over": Decimal("1.90"), "under": Decimal("2.00")},
        )
        _add_historical_market_pair_at_target(
            session,
            match,
            target_minutes=target_minutes,
            market_type="match_winner",
            line=Decimal("0.00"),
            outcomes={"home": Decimal("2.10"), "draw": Decimal("3.25"), "away": Decimal("3.40")},
        )
    _add_complete_historical_odds(session, match)
    session.commit()

    report = build_paper_recommendation_queue(
        session,
        now=datetime(2026, 5, 31, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        start_time=datetime(2026, 5, 30, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_time=datetime(2026, 5, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
        scorer=lambda row: PaperQueueScore(
            side="away_cover",
            model_probability=Decimal("0.6500"),
            market_probability=Decimal("0.5181"),
            edge=Decimal("0.1319"),
            model_name="fake_hgb",
        ),
    )

    assert report.candidate_count == 0
    assert report.rows == []
    assert report.discarded_by_robustness_match_count == 1
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_queue_service.py::test_confirmed_under_mid_275_uses_filter_mode tests/test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_discovers_latest_only_candidate_when_fixed_targets_are_robust tests/test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_filters_finished_candidate_like_scheduled -q
```

Expected: FAIL because confirmed-under is still observe mode, latest-only union discovery is not implemented, finished filtering parity is not implemented, and the report has no discard count.

- [ ] **Step 5: Commit the failing tests**

```powershell
git add tests/test_paper_recommendation_queue_service.py
git commit -m "新增纸面多时点发现验收测试"
```

---

### Task 2: Implement Multi-Timepoint Discovery In The Queue Service

**Files:**
- Modify: `src/icewine_prediction/execution_robustness_rules.py`
- Modify: `src/icewine_prediction/paper_recommendation_queue_service.py`
- Test: `tests/test_paper_recommendation_queue_service.py`

- [ ] **Step 1: Change confirmed-under to filter mode**

In `src/icewine_prediction/execution_robustness_rules.py`, remove `mode="observe"` from the `TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY` rule so it uses the dataclass default:

```python
    TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY: SelectedExecutionRobustnessRule(
        strategy_key=TOTAL_GOALS_HGB_CONFIRMED_UNDER_MID_275_V1_KEY,
        primary_target=15,
        min_seen_count=3,
        min_edge=Decimal("0.1200"),
        allow_bucket_changed=True,
        allow_line_changed=True,
        require_side_unchanged=True,
    ),
```

- [ ] **Step 2: Add report discard count**

In `PaperRecommendationQueueReport`, add:

```python
    discarded_by_robustness_match_count: int = 0
```

When constructing the report in `build_paper_recommendation_queue`, collect rows and discard match ids explicitly:

```python
    rows = []
    discarded_by_robustness_match_ids: set[int] = set()
    for match in matches:
        match_rows, match_discarded = _build_queue_rows_with_diagnostics(
            match,
            scorer=model_scorer,
            edge_threshold=threshold,
            display_name_service=display_name_service,
            historical_snapshots=historical_snapshots_by_match_id.get(match.id, []),
            team_prior_states=team_prior_states,
        )
        rows.extend(match_rows)
        if match_discarded:
            discarded_by_robustness_match_ids.add(match.id)
```

Pass this into the report:

```python
        discarded_by_robustness_match_count=len(discarded_by_robustness_match_ids),
```

Keep `_build_queue_rows` as a compatibility wrapper:

```python
def _build_queue_rows(...) -> list[PaperQueueRow]:
    rows, _ = _build_queue_rows_with_diagnostics(...)
    return rows
```

- [ ] **Step 3: Add internal discovery dataclasses**

Near `_ExecutionRobustnessEvaluation`, add:

```python
@dataclass(frozen=True)
class _TimepointFeature:
    label: str
    target: int | None
    snapshots: list[HistoricalOddsSnapshot]
    feature_row: dict[str, str]


@dataclass(frozen=True)
class _DiscoveredStrategyRow:
    row: PaperQueueRow
    target: int | None
```

- [ ] **Step 4: Build timepoint features once per match**

Add:

```python
def _timepoint_features_for_match(
    match: Match,
    *,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
) -> list[_TimepointFeature]:
    features = []
    for target in DEFAULT_EXECUTION_ROBUSTNESS_TARGETS:
        target_snapshots = _historical_snapshots_for_execution_target(
            match,
            historical_snapshots=historical_snapshots,
            target_minutes_before_kickoff=target,
            tolerance_minutes=DEFAULT_EXECUTION_ROBUSTNESS_TOLERANCE_MINUTES,
        )
        if not target_snapshots:
            continue
        features.append(
            _TimepointFeature(
                label=f"T-{target}",
                target=target,
                snapshots=target_snapshots,
                feature_row=_live_feature_row(
                    match,
                    historical_snapshots=target_snapshots,
                    team_prior_states=team_prior_states,
                ),
            )
        )
    latest_snapshots = _latest_historical_snapshots_for_match(match, historical_snapshots)
    if latest_snapshots:
        features.append(
            _TimepointFeature(
                label="latest_historical",
                target=None,
                snapshots=latest_snapshots,
                feature_row=_live_feature_row(
                    match,
                    historical_snapshots=latest_snapshots,
                    team_prior_states=team_prior_states,
                ),
            )
        )
    return features
```

Add `_latest_historical_snapshots_for_match` using the existing latest selection from `baseline_paper_discovery_alignment_service._select_latest_pre_kickoff_pair` or an equivalent local helper that selects the latest pre-kickoff pair per market and returns `_snapshots_from_pair`.

- [ ] **Step 5: Discover strategy rows from timepoint features**

Add:

```python
def _discover_strategy_rows_for_timepoints(
    match: Match,
    *,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshot_count: int,
    timepoint_features: list[_TimepointFeature],
) -> list[_DiscoveredStrategyRow]:
    discovered = []
    for timepoint in timepoint_features:
        for row in _strategy_rows_for_feature_row(
            match,
            scorer=scorer,
            edge_threshold=edge_threshold,
            feature_row=timepoint.feature_row,
            display_name_service=display_name_service,
            historical_snapshots=timepoint.snapshots,
            odds_source="oddspapi_historical",
            execution_target=timepoint.label,
            historical_snapshot_count=historical_snapshot_count,
        ):
            if row.status == "candidate":
                discovered.append(_DiscoveredStrategyRow(row=row, target=timepoint.target))
    return discovered
```

- [ ] **Step 6: Evaluate union candidates and return only kept rows**

Add:

```python
def _multi_timepoint_candidate_rows(
    match: Match,
    *,
    scorer: Callable[[dict[str, str]], PaperQueueScoreResult],
    edge_threshold: Decimal,
    display_name_service: DisplayNameService | None,
    historical_snapshots: list[HistoricalOddsSnapshot],
    team_prior_states: dict[tuple[int, str], _TeamPriorState] | None,
) -> tuple[list[PaperQueueRow], bool]:
    timepoint_features = _timepoint_features_for_match(
        match,
        historical_snapshots=historical_snapshots,
        team_prior_states=team_prior_states,
    )
    if not timepoint_features:
        return [], False
    discovered = _discover_strategy_rows_for_timepoints(
        match,
        scorer=scorer,
        edge_threshold=edge_threshold,
        display_name_service=display_name_service,
        historical_snapshot_count=len(historical_snapshots),
        timepoint_features=timepoint_features,
    )
    by_key: dict[tuple[str, str, str | None], list[_DiscoveredStrategyRow]] = {}
    for item in discovered:
        by_key.setdefault((item.row.strategy_key, item.row.market_type, item.row.side), []).append(item)
    kept_rows = []
    discarded = False
    for items in by_key.values():
        representative = _representative_discovered_row(items)
        observations = [
            _ExecutionRobustnessObservation(
                target=item.target,
                side=item.row.side,
                line=item.row.line,
                line_bucket=item.row.line_bucket,
                edge=item.row.edge,
            )
            for item in items
            if item.target is not None and item.row.edge is not None
        ]
        evaluation = _evaluate_execution_robustness(
            observations,
            rule=DEFAULT_SELECTED_ROBUSTNESS_RULES[representative.strategy_key],
        )
        if evaluation.status == "kept":
            kept_rows.append(_row_with_robustness(representative, evaluation))
        else:
            discarded = True
    return kept_rows, discarded
```

Implement `_representative_discovered_row` with the preference from the spec: primary target row, highest-edge fixed target, highest-edge latest. Implement `_row_with_robustness` by copying the existing field update logic from `_apply_execution_robustness_to_row` without adding filtered risk tags.

Use `DEFAULT_SELECTED_ROBUSTNESS_RULES.get(...)`; if no rule exists, keep the representative row unchanged. Do not include `target=None` latest observations in fixed-target robustness observations.

- [ ] **Step 7: Route historical matches through the new path**

Refactor `_build_queue_rows` into `_build_queue_rows_with_diagnostics`. After historical snapshots are selected and diagnostic `no_odds` / `odds_status_not_ready` checks pass, call `_multi_timepoint_candidate_rows` for `odds_source == "oddspapi_historical"`.

Return `(kept_rows, discarded)` for historical matches. Do not append `robustness_filtered` rows for discarded candidates.

Keep the live snapshot path using the existing one-row scoring behavior and no robustness hard filter.

- [ ] **Step 8: Run focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_queue_service.py::test_confirmed_under_mid_275_uses_filter_mode tests/test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_discovers_latest_only_candidate_when_fixed_targets_are_robust tests/test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_filters_finished_candidate_like_scheduled tests/test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_reuses_robustness_target_scores_across_strategy_rows -q
```

Expected: PASS.

- [ ] **Step 9: Commit implementation**

```powershell
git add src/icewine_prediction/execution_robustness_rules.py src/icewine_prediction/paper_recommendation_queue_service.py tests/test_paper_recommendation_queue_service.py
git commit -m "接入纸面多时点候选发现"
```

---

### Task 3: Expose Simple Discard Diagnostics

**Files:**
- Modify: `src/icewine_prediction/paper_recommendation_queue_service.py`
- Modify: `src/icewine_prediction/web_api.py`
- Modify: `tests/test_paper_recommendation_queue_service.py`
- Modify: `tests/test_web_console_api.py`
- Optional Modify: `web/src/types.ts`

- [ ] **Step 1: Format discard count in text report**

In `format_paper_recommendation_queue_report`, add this row to the summary table:

```python
        f"| Robustness discarded matches | {report.discarded_by_robustness_match_count} |",
```

- [ ] **Step 2: Assert text report includes discard count**

In `test_build_paper_recommendation_queue_filters_finished_candidate_like_scheduled`, add:

```python
    text = format_paper_recommendation_queue_report(report)
    assert "Robustness discarded matches" in text
    assert "| Robustness discarded matches | 1 |" in text
```

- [ ] **Step 3: Add discard count to API payloads**

In `build_paper_recommendation_queue_payload`, add:

```python
        "discarded_by_robustness_match_count": report.discarded_by_robustness_match_count,
```

In `build_paper_recommendation_diagnostics_payload`, add:

```python
        "discarded_by_robustness_match_count": report.discarded_by_robustness_match_count,
```

- [ ] **Step 4: Add API test assertions**

In `tests/test_web_console_api.py`, update the paper queue/workspace tests that assert diagnostics payloads. Add assertions like:

```python
assert "discarded_by_robustness_match_count" in payload
```

and for workspace diagnostics:

```python
assert "discarded_by_robustness_match_count" in workspace["diagnostics"]
```

Use existing tests around lines that already assert `candidate_count` and `status_counts`.

- [ ] **Step 5: Update TypeScript type if required**

If frontend type checking fails, add this optional field to the queue/workspace diagnostics type in `web/src/types.ts`:

```typescript
discarded_by_robustness_match_count?: number;
```

- [ ] **Step 6: Run backend and frontend focused checks**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py -q
```

If `web/src/types.ts` changed, also run:

```powershell
cd web
npm test -- paperRecommendationWorkspace.test.ts apiClient.test.ts
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit diagnostics**

```powershell
git add src/icewine_prediction/paper_recommendation_queue_service.py src/icewine_prediction/web_api.py tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py web/src/types.ts
git commit -m "透出纸面鲁棒舍弃比赛统计"
```

---

### Task 4: Regression Verification And Handoff Notes

**Files:**
- Modify if needed: `docs/交接/20260603-paper-robustness-handoff.md`

- [ ] **Step 1: Run related backend tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py tests/test_baseline_execution_robustness_filter_service.py tests/test_baseline_paper_discovery_alignment_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks if any web files changed**

Run:

```powershell
cd web
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 3: Update handoff doc if behavior changed materially**

If `docs/交接/20260603-paper-robustness-handoff.md` still says finished filtered candidates are preserved, update that section to say finished backfill now simulates scheduled behavior and discards non-robust candidates before candidate output.

- [ ] **Step 4: Run final status and diff checks**

Run:

```powershell
git status --short
git diff --check
```

Expected: only intended tracked changes before final commit; `git diff --check` has no errors.

- [ ] **Step 5: Commit final docs if changed**

If Task 4 changed docs:

```powershell
git add docs/交接/20260603-paper-robustness-handoff.md
git commit -m "更新纸面发现接入口径交接"
```

---

## Self-Review

- Spec coverage: the plan covers multi-timepoint union discovery, fixed-target robustness, scheduled/finished parity, confirmed-under filter mode, simple discard match count, API diagnostics, and performance guard.
- Placeholder scan: no `TBD` or open-ended implementation steps remain; each task names files, code shape, commands, and expected outcomes.
- Type consistency: the plan uses existing `PaperQueueRow`, `PaperRecommendationQueueReport`, `PaperQueueScore`, `HistoricalOddsSnapshot`, and `DEFAULT_SELECTED_ROBUSTNESS_RULES` names consistently.

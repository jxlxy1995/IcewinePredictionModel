# Total Goals v3 Signal Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a research-only total-goals v3 signal report that evaluates direction and total-line bucket candidates without promoting them into the paper workflow.

**Architecture:** Reuse the existing total-goals candidate builder and walk-forward fold logic, then add a focused v3 report service for threshold-grid evaluation, overlap analysis, and candidate ratings. Expose it through CLI and training full-refresh experiments so generated reports follow the existing model-experiment pattern.

**Tech Stack:** Python, dataclasses, Decimal, CSV feature files, Typer CLI, pytest.

---

## File Structure

- Create `src/icewine_prediction/baseline_total_goals_v3_signal_research_service.py`
  - Owns the v3 candidate grid, gate evaluation, overlap analysis, markdown formatting, and report writing.
- Modify `src/icewine_prediction/cli.py`
  - Adds `samples baseline-total-goals-v3-signal-research`.
- Modify `src/icewine_prediction/training_orchestration_service.py`
  - Adds the v3 report to full-refresh experiments.
- Create `tests/test_baseline_total_goals_v3_signal_research_service.py`
  - Tests candidate rating gates, overlap metrics, and markdown output.
- Modify `tests/test_samples_cli.py`
  - Tests the new CLI command delegates to the service and writes the report.
- Modify `tests/test_training_orchestration_service.py`
  - Tests default full-refresh experiments include the v3 report.

## Tasks

### Task 1: Add v3 Research Service

**Files:**
- Create: `src/icewine_prediction/baseline_total_goals_v3_signal_research_service.py`
- Test: `tests/test_baseline_total_goals_v3_signal_research_service.py`

- [ ] **Step 1: Write tests for ratings and overlap**

Create tests that build small fold reports from synthetic `SandboxCandidate` objects. Assert:

- A candidate with 30+ bets, 4 positive ROI folds, ROI >= 0.0500, and worst fold ROI >= -0.2000 is `promotable`.
- A candidate with positive ROI but insufficient stability is `watchlist`.
- A weak candidate is `rejected`.
- A candidate matching the v2 baseline reports nonzero overlap and incremental metrics.

- [ ] **Step 2: Implement dataclasses and evaluation helpers**

Add dataclasses for:

- `TotalGoalsV3SignalCandidateSummary`
- `TotalGoalsV3SideBucketSummary`
- `BaselineTotalGoalsV3SignalResearchReport`

Implement:

- `build_baseline_total_goals_v3_signal_research_report`
- `write_baseline_total_goals_v3_signal_research_report`
- `format_baseline_total_goals_v3_signal_research_report`

- [ ] **Step 3: Run focused service tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_baseline_total_goals_v3_signal_research_service.py -q
```

Expected: all tests pass.

### Task 2: Add CLI Command

**Files:**
- Modify: `src/icewine_prediction/cli.py`
- Modify: `tests/test_samples_cli.py`

- [ ] **Step 1: Write CLI delegation test**

Patch `build_baseline_total_goals_v3_signal_research_report` and `write_baseline_total_goals_v3_signal_research_report`. Invoke:

```powershell
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_samples_cli.py -q
```

Expected failing test before implementation.

- [ ] **Step 2: Add command**

Add `samples baseline-total-goals-v3-signal-research` with defaults:

- csv path: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`
- report path: `docs/模型实验/20260529-baseline-total-goals-v3-signal-research.md`

Expose options for thresholds, train ratio, validation ratio, and fold count.

- [ ] **Step 3: Run CLI tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_samples_cli.py -q
```

Expected: all tests pass.

### Task 3: Add Full-Refresh Experiment

**Files:**
- Modify: `src/icewine_prediction/training_orchestration_service.py`
- Modify: `tests/test_training_orchestration_service.py`

- [ ] **Step 1: Write orchestration test**

Assert `build_default_training_experiments()` includes key `total_goals_v3_signal_research`.

- [ ] **Step 2: Add experiment writer**

Import the v3 service and add a `TrainingExperiment` with:

- key: `total_goals_v3_signal_research`
- report filename: `baseline-total-goals-v3-signal-research.md`
- dynamic feature CSV input

- [ ] **Step 3: Run orchestration tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_training_orchestration_service.py -q
```

Expected: all tests pass.

### Task 4: Generate Current Report And Verify

**Files:**
- Generated: `docs/模型实验/20260602-2036-baseline-total-goals-v3-signal-research.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests\test_baseline_total_goals_v3_signal_research_service.py tests\test_samples_cli.py tests\test_training_orchestration_service.py -q
```

- [ ] **Step 2: Generate report from latest dynamic feature CSV**

Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli samples baseline-total-goals-v3-signal-research `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260602-2036.csv `
  --report-path docs/模型实验/20260602-2036-baseline-total-goals-v3-signal-research.md
```

- [ ] **Step 3: Review generated report**

Open the generated markdown and summarize:

- promotable candidates
- watchlist candidates
- rejected high-volume buckets
- overlap with current v2

- [ ] **Step 4: Commit**

Commit spec, plan, implementation, tests, and generated report in one focused commit.

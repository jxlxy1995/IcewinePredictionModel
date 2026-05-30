# Training Orchestration Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Web-controlled `更新训练与模型报告` workflow that refreshes training artifacts, records run metadata, and shows the latest update time plus the last trained match summary on the `模型训练` page.

**Architecture:** Add a backend `training_runs` table and a focused orchestration service that runs the existing dataset, QA, market baseline, feature, dynamic feature, and away-cover stability builders in order. Expose start/latest-run API endpoints and extend the existing training workspace payload, then add typed frontend helpers and UI state on the current model training page.

**Tech Stack:** Python, SQLAlchemy, FastAPI, pytest, React, TypeScript, Vitest.

---

## File Structure

- Modify `src/icewine_prediction/models.py`: add `TrainingRun`.
- Create `src/icewine_prediction/training_orchestration_service.py`: run lifecycle, step execution, snapshot paths, latest-run payload data.
- Modify `src/icewine_prediction/web_api.py`: add full-refresh/latest-run endpoints, background runner wiring, and `latest_run` inside the training workspace payload.
- Create `tests/test_training_orchestration_service.py`: service-level orchestration tests.
- Modify `tests/test_web_console_api.py`: API endpoint and workspace tests.
- Modify `web/src/types.ts`: add training run and step payload types.
- Modify `web/src/apiClient.ts`: add `startTrainingFullRefresh` and `loadLatestTrainingRun`.
- Modify `web/src/modelTrainingWorkspace.ts`: add formatting helpers for latest run cards, step labels, and last trained match summary.
- Modify `web/src/modelTrainingWorkspace.test.ts`: frontend helper tests.
- Modify `web/src/mockData.ts`: add mock `latest_run`.
- Modify `web/src/pages/DashboardPage.tsx`: add orchestration panel, polling, and disabled/running/error states.
- Modify `web/src/styles.css`: compact top-panel and step-list styling if the existing classes are insufficient.

## Task 1: Backend Run Model

**Files:**
- Modify: `src/icewine_prediction/models.py`
- Test: `tests/test_training_orchestration_service.py`

- [ ] Create `tests/test_training_orchestration_service.py` with a failing model persistence test:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import TrainingRun


def test_training_run_persists_lifecycle_metadata():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        run = TrainingRun(
            run_type="full_refresh",
            status="running",
            started_at=datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
            snapshot_tag="20260530-1323",
            current_step="baseline_dataset",
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)
        assert saved is not None
        assert saved.run_type == "full_refresh"
        assert saved.status == "running"
        assert saved.snapshot_tag == "20260530-1323"
        assert saved.current_step == "baseline_dataset"
```

- [ ] Run the focused test and confirm it fails because `TrainingRun` is not defined:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_training_orchestration_service.py -q
```

- [ ] Add `TrainingRun` to `src/icewine_prediction/models.py` with columns matching the design:

```python
class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_tag: Mapped[str] = mapped_column(String(40), nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(80))
    error_step: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    dataset_path: Mapped[str | None] = mapped_column(String(255))
    dataset_report_path: Mapped[str | None] = mapped_column(String(255))
    qa_report_path: Mapped[str | None] = mapped_column(String(255))
    market_baseline_report_path: Mapped[str | None] = mapped_column(String(255))
    feature_path: Mapped[str | None] = mapped_column(String(255))
    feature_report_path: Mapped[str | None] = mapped_column(String(255))
    dynamic_feature_path: Mapped[str | None] = mapped_column(String(255))
    dynamic_feature_report_path: Mapped[str | None] = mapped_column(String(255))
    away_cover_stability_report_path: Mapped[str | None] = mapped_column(String(255))
    dataset_rows: Mapped[int | None] = mapped_column(Integer)
    eligible_matches: Mapped[int | None] = mapped_column(Integer)
    complete_matches: Mapped[int | None] = mapped_column(Integer)
    coverage_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    last_trained_match_id: Mapped[int | None] = mapped_column(Integer)
    last_trained_match_summary: Mapped[str | None] = mapped_column(String(255))
    last_trained_kickoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_complete_matches: Mapped[int | None] = mapped_column(Integer)
```

- [ ] Re-run the focused test and confirm it passes.

## Task 2: Orchestration Service Lifecycle

**Files:**
- Create: `src/icewine_prediction/training_orchestration_service.py`
- Test: `tests/test_training_orchestration_service.py`

- [ ] Add failing tests for run creation, latest-run lookup, and single-running-run guard:

```python
from icewine_prediction.training_orchestration_service import (
    TrainingRunAlreadyRunning,
    create_training_run,
    get_latest_training_run,
)


def test_create_training_run_uses_beijing_snapshot_tag():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    clock = lambda: datetime(2026, 5, 30, 13, 23, 45, tzinfo=ZoneInfo("Asia/Shanghai"))

    with session_factory() as session:
        run = create_training_run(session, clock=clock)
        session.commit()

    assert run.status == "running"
    assert run.run_type == "full_refresh"
    assert run.snapshot_tag == "20260530-1323"
    assert run.current_step == "queued"


def test_create_training_run_rejects_existing_running_run():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    clock = lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai"))

    with session_factory() as session:
        first = create_training_run(session, clock=clock)
        session.commit()
        try:
            create_training_run(session, clock=clock)
        except TrainingRunAlreadyRunning as error:
            assert error.active_run_id == first.id
        else:
            raise AssertionError("expected TrainingRunAlreadyRunning")


def test_get_latest_training_run_returns_newest_started_run():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        session.add_all([
            TrainingRun(
                run_type="full_refresh",
                status="success",
                started_at=datetime(2026, 5, 30, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                snapshot_tag="20260530-0900",
            ),
            TrainingRun(
                run_type="full_refresh",
                status="failed",
                started_at=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                snapshot_tag="20260530-1300",
            ),
        ])
        session.commit()
        latest = get_latest_training_run(session)

    assert latest is not None
    assert latest.snapshot_tag == "20260530-1300"
```

- [ ] Run the focused test file and confirm missing service failures.
- [ ] Implement `TrainingRunAlreadyRunning`, `create_training_run`, and `get_latest_training_run`.
- [ ] Re-run the focused tests and confirm they pass.

## Task 3: Snapshot Paths And Last Trained Match

**Files:**
- Modify: `src/icewine_prediction/training_orchestration_service.py`
- Test: `tests/test_training_orchestration_service.py`

- [ ] Add failing tests for snapshot paths and latest-match extraction from the generated dataset CSV:

```python
from pathlib import Path

from icewine_prediction.training_orchestration_service import (
    build_training_snapshot_paths,
    extract_last_trained_match_summary,
)


def test_build_training_snapshot_paths_uses_snapshot_tag(tmp_path):
    paths = build_training_snapshot_paths(tmp_path, "20260530-1323")

    assert paths.dataset_path == tmp_path / "local_data/training/baseline_main_leagues_20260530-1323.csv"
    assert paths.feature_path == tmp_path / "local_data/training/baseline_features_main_leagues_20260530-1323.csv"
    assert paths.dynamic_feature_path == tmp_path / "local_data/training/baseline_dynamic_features_main_leagues_20260530-1323.csv"
    assert paths.away_cover_stability_report_path == tmp_path / "docs/模型实验/20260530-1323-baseline-away-cover-stability-v1.md"


def test_extract_last_trained_match_summary_uses_latest_kickoff_and_display_names(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
        "1,2026-05-29T20:00:00+08:00,J1 League,Kobe,Tokyo,1,1\n"
        "2,2026-05-30T18:00:00+08:00,J1 League,Kashima,Nagoya,2,0\n",
        encoding="utf-8",
    )

    summary = extract_last_trained_match_summary(
        csv_path,
        display_league=lambda value: "日职联" if value == "J1 League" else value,
        display_team=lambda value: {"Kashima": "鹿岛鹿角", "Nagoya": "名古屋鲸八"}.get(value, value),
    )

    assert summary.match_id == 2
    assert summary.kickoff_time.isoformat() == "2026-05-30T18:00:00+08:00"
    assert summary.text == "日职联 鹿岛鹿角 2-0 名古屋鲸八"
```

- [ ] Implement `TrainingSnapshotPaths`, `build_training_snapshot_paths`, `LastTrainedMatchSummary`, and `extract_last_trained_match_summary`.
- [ ] Re-run the focused tests and confirm they pass.

## Task 4: Pipeline Runner With Injectable Steps

**Files:**
- Modify: `src/icewine_prediction/training_orchestration_service.py`
- Test: `tests/test_training_orchestration_service.py`

- [ ] Add a failing success-path test using fake step functions:

```python
from icewine_prediction.training_orchestration_service import (
    TrainingOrchestrationSteps,
    run_training_full_refresh,
)


def test_run_training_full_refresh_records_step_order_and_success(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls: list[str] = []

    def write_dataset(session, paths):
        calls.append("baseline_dataset")
        paths.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        paths.dataset_path.write_text(
            "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
            "7,2026-05-30T18:00:00+08:00,J1 League,Kobe,Kashima,1,0\n",
            encoding="utf-8",
        )
        return {"eligible_matches": 10, "complete_matches": 1, "coverage_ratio": "0.1000"}

    def touch(name):
        def step(paths):
            calls.append(name)
        return step

    with session_factory() as session:
        run = create_training_run(
            session,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        session.commit()
        run_id = run.id

    steps = TrainingOrchestrationSteps(
        write_dataset=write_dataset,
        write_qa=touch("dataset_qa"),
        write_market_baseline=touch("market_baseline"),
        write_feature_set=touch("feature_set"),
        write_dynamic_feature_set=touch("dynamic_feature_set"),
        write_away_cover_stability=touch("away_cover_stability"),
    )

    run_training_full_refresh(
        session_factory,
        run_id,
        base_dir=tmp_path,
        steps=steps,
        display_league=lambda value: "日职联" if value == "J1 League" else value,
        display_team=lambda value: {"Kobe": "神户胜利船", "Kashima": "鹿岛鹿角"}.get(value, value),
        clock=lambda: datetime(2026, 5, 30, 13, 24, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)

    assert calls == [
        "baseline_dataset",
        "dataset_qa",
        "market_baseline",
        "feature_set",
        "dynamic_feature_set",
        "away_cover_stability",
    ]
    assert saved.status == "success"
    assert saved.dataset_rows == 1
    assert saved.complete_matches == 1
    assert saved.last_trained_match_id == 7
    assert saved.last_trained_match_summary == "日职联 神户胜利船 1-0 鹿岛鹿角"
```

- [ ] Add a failing failure-path test that raises in `write_feature_set` and asserts `status="failed"`, `error_step="feature_set"`, and existing earlier paths remain recorded.
- [ ] Implement `TrainingOrchestrationSteps`, default production step wrappers around existing builder/writer functions, and `run_training_full_refresh`.
- [ ] Keep each step updating `current_step` before running so the Web page can show progress.
- [ ] Re-run the service tests and confirm they pass.

## Task 5: Backend API Endpoints

**Files:**
- Modify: `src/icewine_prediction/web_api.py`
- Test: `tests/test_web_console_api.py`

- [ ] Add failing tests for `POST /api/training/runs/full-refresh`, `GET /api/training/runs/latest`, and conflict on a second running run:

```python
def test_web_console_api_starts_training_full_refresh(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    started: list[int] = []

    def fake_background_runner(run_id: int):
        started.append(run_id)

    client = TestClient(
        create_web_app(
            session_factory=session_factory,
            log_dir=tmp_path,
            training_full_refresh_runner=fake_background_runner,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )

    response = client.post("/api/training/runs/full-refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["snapshot_tag"] == "20260530-1323"
    assert started == [payload["id"]]


def test_web_console_api_returns_latest_training_run(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            TrainingRun(
                run_type="full_refresh",
                status="success",
                started_at=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                finished_at=datetime(2026, 5, 30, 13, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
                snapshot_tag="20260530-1300",
                dataset_rows=5330,
                last_trained_match_summary="日职联 神户胜利船 1-0 鹿岛鹿角",
            )
        )
        session.commit()

    client = TestClient(create_web_app(session_factory=session_factory, log_dir=tmp_path))
    response = client.get("/api/training/runs/latest")

    assert response.status_code == 200
    assert response.json()["snapshot_tag"] == "20260530-1300"
    assert response.json()["last_trained_match_summary"] == "日职联 神户胜利船 1-0 鹿岛鹿角"
```

- [ ] Modify `create_web_app` to accept a `training_full_refresh_runner` injection for tests.
- [ ] Add payload builder for `TrainingRun` that serializes decimals and Beijing-time datetimes.
- [ ] Add the two endpoints.
- [ ] Extend `build_training_workspace_payload` to accept optional `latest_run` data and return it as `latest_run`.
- [ ] Make the `POST` endpoint return `409` if `create_training_run` raises `TrainingRunAlreadyRunning`.
- [ ] Run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_training_orchestration_service.py tests/test_web_console_api.py -q
```

## Task 6: Frontend Types, Client, And Helpers

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/apiClient.ts`
- Modify: `web/src/modelTrainingWorkspace.ts`
- Modify: `web/src/modelTrainingWorkspace.test.ts`
- Modify: `web/src/mockData.ts`

- [ ] Add failing helper tests for latest-run cards, running step labels, and failure labels:

```ts
import {
  buildTrainingRunCards,
  formatTrainingRunStatus,
  formatTrainingRunStep
} from "./modelTrainingWorkspace";

it("formats latest training run cards", () => {
  const cards = buildTrainingRunCards({
    id: 3,
    run_type: "full_refresh",
    status: "success",
    started_at: "2026-05-30T13:23:00+08:00",
    finished_at: "2026-05-30T13:28:00+08:00",
    snapshot_tag: "20260530-1323",
    current_step: "finalize",
    error_step: null,
    error_message: null,
    dataset_rows: 5330,
    coverage_ratio: "0.8912",
    last_trained_match_summary: "日职联 神户胜利船 1-0 鹿岛鹿角",
    last_trained_kickoff_time: "2026-05-30T18:00:00+08:00",
    artifact_paths: {}
  });

  expect(cards).toContainEqual({ label: "最近更新", value: "2026-05-30 13:28" });
  expect(cards).toContainEqual({ label: "训练样本", value: "5,330" });
  expect(cards).toContainEqual({ label: "最后入训", value: "日职联 神户胜利船 1-0 鹿岛鹿角" });
});

it("formats run status and step labels", () => {
  expect(formatTrainingRunStatus("running")).toBe("运行中");
  expect(formatTrainingRunStatus("success")).toBe("成功");
  expect(formatTrainingRunStatus("failed")).toBe("失败");
  expect(formatTrainingRunStep("dynamic_feature_set")).toBe("动态特征");
});
```

- [ ] Add `TrainingRunStatus`, `TrainingRunStep`, and `TrainingRun` to `web/src/types.ts`.
- [ ] Extend `TrainingWorkspace` with `latest_run: TrainingRun | null`.
- [ ] Add API client functions:

```ts
export async function startTrainingFullRefresh(): Promise<TrainingRun> {
  return await postJson<TrainingRun>("/api/training/runs/full-refresh", {});
}

export async function loadLatestTrainingRun(): Promise<TrainingRun | null> {
  return await getJsonOrFallback<TrainingRun | null>("/api/training/runs/latest", null);
}
```

- [ ] Implement `buildTrainingRunCards`, `formatTrainingRunStatus`, and `formatTrainingRunStep` in `web/src/modelTrainingWorkspace.ts`.
- [ ] Update `web/src/mockData.ts` so the mock training workspace includes a representative `latest_run`.
- [ ] Run:

```powershell
cd web
npm test -- modelTrainingWorkspace.test.ts apiClient.test.ts
```

## Task 7: Frontend Page Wiring

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`
- Modify: `web/src/styles.css`

- [ ] Add the orchestration panel at the top of `ModelTrainingView`:
  - Button text: `更新训练与模型报告`
  - Show latest run status, latest finished time, dataset rows, coverage ratio, and last trained match.
  - Show generated artifact paths from `latest_run.artifact_paths`.
  - Show step list with current/running state.
- [ ] Wire the primary button to `startTrainingFullRefresh`.
- [ ] Disable the primary button while `trainingAction === "full-refresh"` or `workspace.latest_run?.status === "running"`.
- [ ] Poll `loadTrainingWorkspace` every few seconds while the latest run is `running`; stop polling when the run becomes `success` or `failed`.
- [ ] Keep the existing granular buttons for `生成训练集`, `执行 QA`, and `市场基准`, but place them below the orchestration panel.
- [ ] Add failure text from `latest_run.error_step` and `latest_run.error_message`.
- [ ] Run:

```powershell
cd web
npm test -- modelTrainingWorkspace.test.ts apiClient.test.ts
npm run build
```

## Task 8: Verification

**Files:**
- Review all touched backend/frontend files.

- [ ] Run backend verification:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_training_orchestration_service.py tests/test_web_console_api.py -q
```

- [ ] Run frontend verification:

```powershell
cd web
npm test -- modelTrainingWorkspace.test.ts apiClient.test.ts
npm run build
```

- [ ] Start the local Web stack using the existing project scripts after confirming the other Web-console loading changes have settled.
- [ ] Manually click `模型训练 -> 更新训练与模型报告` against local data.
- [ ] Confirm the page shows Beijing-time latest update, success/failure state, produced paths, and the last trained match summary.

## Self-Review

- Spec coverage: this plan covers the primary Web button, persistent run metadata, latest update time, last trained match summary, step progress, background execution, failed-run handling, no automatic paper-record creation, and frontend display.
- Placeholder scan: no task relies on unspecified behavior; the only deferred items are explicitly out of scope in the design.
- Type consistency: backend uses `TrainingRun`; API/frontend use `TrainingRun`, `latest_run`, and the full-refresh endpoint names consistently.

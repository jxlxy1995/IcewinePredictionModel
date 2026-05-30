# Training Orchestration Console Design

## Context

The Web console already has a `模型训练` view with separate actions for:

- `POST /api/training/baseline-dataset`
- `POST /api/training/baseline-dataset-qa`
- `POST /api/training/market-baseline`

The modeling workflow has grown beyond those three steps. The current manual refresh path also includes feature generation, dynamic feature generation, and at least the away-cover stability report. After finished match results are updated, the user needs one Web-controlled action that refreshes the training artifacts and records enough metadata to answer:

- When was the latest training/model refresh run?
- Did it succeed or fail?
- Which files were produced?
- How many matches entered the latest dataset?
- What is the last match included in training?

## Decisions

- Add one primary Web action on the `模型训练` page named `更新训练与模型报告`.
- Keep the existing granular actions for now, but visually demote them under the full refresh action.
- Add persistent `training_runs` records so the page can show the latest run after reloads.
- Run the refresh in a background task. The button returns a run payload quickly and the page polls the latest run/workspace state.
- Use versioned snapshot output paths for the full refresh, keyed by Beijing date/time, so failed partial runs do not overwrite the latest successful artifacts.
- Do not automatically create paper recommendation records from this refresh. Paper recommendation queue generation and formal record creation stay separate workflows.
- Do not add scheduling, cancellation, WebSocket progress, model deployment, or automatic betting/recommendation automation in v1.

## Training Run Record

Create a `training_runs` table with these fields:

- `id`
- `run_type`: v1 uses `full_refresh`
- `status`: `running`, `success`, or `failed`
- `started_at`
- `finished_at`
- `snapshot_tag`: Beijing-time tag such as `20260530-1323`
- `current_step`: one of the pipeline step keys below
- `error_step`
- `error_message`
- `dataset_path`
- `dataset_report_path`
- `qa_report_path`
- `market_baseline_report_path`
- `feature_path`
- `feature_report_path`
- `dynamic_feature_path`
- `dynamic_feature_report_path`
- `away_cover_stability_report_path`
- `dataset_rows`
- `eligible_matches`
- `complete_matches`
- `coverage_ratio`
- `last_trained_match_id`
- `last_trained_match_summary`
- `last_trained_kickoff_time`
- `new_complete_matches`

All timestamps are stored consistently with the existing database approach. User-facing timestamps in the Web payload are formatted in Beijing time.

## Pipeline

The full refresh runs these steps in order:

1. `baseline_dataset`: build complete three-market enabled-main-league training CSV and dataset audit report.
2. `dataset_qa`: build QA report from the generated dataset CSV.
3. `market_baseline`: build close-market baseline report from the generated dataset CSV.
4. `feature_set`: build baseline feature CSV and feature audit report.
5. `dynamic_feature_set`: build dynamic feature CSV and dynamic feature audit report.
6. `away_cover_stability`: build the current away-cover stability model experiment report from the generated dynamic feature CSV.
7. `finalize`: update the run record with produced paths, row counts, last trained match summary, and success status.

The last trained match is the latest included dataset row by kickoff time. Its summary should include league display name, home team display name, away team display name, score if present, local match id, and Beijing kickoff time.

## Output Paths

The existing fixed paths can remain supported for backwards compatibility, but the full refresh should write versioned outputs:

- `local_data/training/baseline_main_leagues_<snapshot_tag>.csv`
- `docs/数据审计/<snapshot_tag>-baseline-training-dataset.md`
- `docs/数据审计/<snapshot_tag>-baseline-training-dataset-qa.md`
- `local_data/training/baseline_features_main_leagues_<snapshot_tag>.csv`
- `docs/数据审计/<snapshot_tag>-baseline-feature-set-v1.md`
- `local_data/training/baseline_dynamic_features_main_leagues_<snapshot_tag>.csv`
- `docs/数据审计/<snapshot_tag>-baseline-dynamic-feature-set-v1.md`
- `docs/模型实验/<snapshot_tag>-close-market-baseline-evaluation.md`
- `docs/模型实验/<snapshot_tag>-baseline-away-cover-stability-v1.md`

The latest successful `training_runs` row becomes the source of truth for the Web page. The fixed-path workspace can still be displayed as a fallback when no run row exists yet.

## Web UI

On the `模型训练` page, add a top orchestration panel:

- Primary button: `更新训练与模型报告`
- Latest run status: running, success, failed
- Latest updated time in Beijing time
- Snapshot tag
- Dataset rows and coverage ratio
- Last trained match summary
- Last trained match kickoff time in Beijing time
- Produced artifact links or local paths
- Step progress list
- Failed step and error message if a run fails

When a run is `running`, disable the primary button and show the current step. The page can poll `GET /api/training/workspace` or a dedicated latest-run endpoint every few seconds until the run reaches `success` or `failed`.

## API

Add endpoints:

- `POST /api/training/runs/full-refresh`
  - Starts a background full refresh if no run is already running.
  - Returns the new run payload immediately.
- `GET /api/training/runs/latest`
  - Returns the latest run payload, or `null` if none exists.
- Extend `GET /api/training/workspace`
  - Include `latest_run` and derived orchestration cards alongside the current dataset/QA/market baseline payload.

If a full refresh is already running, `POST /api/training/runs/full-refresh` returns `409` with the active run payload or a clear message.

## Error Handling

- A failed step updates the same run row with `status=failed`, `error_step`, `error_message`, and `finished_at`.
- Existing successful artifacts remain valid because the full refresh writes versioned outputs.
- The Web page shows the failure and keeps the latest successful run visible if one exists.
- The service should make the pipeline idempotent enough that a new run can be started after failure without manual cleanup.

## Testing

Backend tests should cover:

- `TrainingRun` creation, running state, success state, and failed state.
- Single-running-run guard.
- Pipeline step order with fake step functions.
- Snapshot-tagged output paths.
- Last trained match extraction and Beijing-time display summary.
- Workspace payload including `latest_run`.
- API success, conflict, and failure responses.
- No automatic `paper_recommendation_records` creation.

Frontend tests should cover:

- Latest run summary cards.
- Disabled primary button while running.
- Step list formatting.
- Failure message display.
- Last trained match summary display.
- API client calls for starting and loading a run.

## Out Of Scope

- Automatic paper recommendation record creation.
- Scheduler/cron support.
- Cancellation or pause/resume.
- WebSocket/SSE progress streaming.
- Model deployment.
- Changing the underlying model strategy or thresholds.

# Paper Automation Task Queue Design

## Context

The user needs one-off automation when they cannot operate the Web console manually.
The common workflow is:

1. Use the match list page to confirm a kickoff time has target matches.
2. Create a one-off task before leaving the computer.
3. At the trigger time, automatically run odds backfill, refresh paper candidates, batch-record recordable candidates, and push the result to the phone through Bark.

The first version should be intentionally small. It should not change match-list behavior or add match preview/selection UI.

## Goals

- Add a Web-managed one-off paper automation task queue.
- Let the match list page create a task with only two pieces of business input:
  - task trigger time
  - target match kickoff window
- Add a dedicated automation task page for task state, details, cancellation, and Bark delivery diagnosis.
- Execute tasks while the Web backend is running.
- Keep tasks globally serial to reduce OddsPapi/API-Football request and state risk.
- Send Bark notifications for success with records, success with no candidates, partial odds failures, task failures, and notification failures where possible.
- Ensure every recommendation successfully selected into the final recorded paper groups appears in Bark. Do not truncate recorded recommendations.
- Ensure Bark recommendation lines use the same confidence score and suggested stake units as the Web paper recommendation record page.

## Non-Goals

- No recurring cron-like task templates in v1.
- No per-league, search, status, or selected-row filtering in v1.
- No match preview inside the automation task creation dialog.
- No manual Bark key entry in the Web UI.
- No cancellation of running tasks.
- No separate automation worker process in v1.

## Data Model

Add `paper_automation_tasks`.

Fields:

- `id`
- `created_at`
- `updated_at`
- `created_by`: fixed to `web` in v1
- `trigger_at`
- `match_window_start`
- `match_window_end`
- `status`
- `notification_status`
- `notification_error`
- `started_at`
- `finished_at`
- `missed_at`
- `cancelled_at`
- `error_message`
- `result_payload`: JSON text with execution summaries and notification payloads

The task does not store Bark URL, action chain, league filters, search filters, or selected match IDs in v1.

### Task Status

Main status:

- `pending`
- `running`
- `success`
- `failed`
- `missed`
- `cancelled`

Transitions:

```text
pending -> running -> success
pending -> running -> failed
pending -> missed
pending -> cancelled
```

Notification status:

- `not_configured`
- `pending`
- `sent`
- `failed`
- `skipped`

Bark delivery must not redefine the main task outcome. If the paper workflow succeeds but Bark fails, store:

```text
status = success
notification_status = failed
notification_error = <reason>
```

## Configuration

Use local `.env` / environment values. Do not store secrets in Git.

```env
BARK_PUSH_URL=https://api.day.app/xxxxxx
PAPER_AUTOMATION_GRACE_MINUTES=20
PAPER_AUTOMATION_POLL_SECONDS=20
```

Defaults:

- `PAPER_AUTOMATION_GRACE_MINUTES`: `20`
- `PAPER_AUTOMATION_POLL_SECONDS`: `20`

The poll interval can be loosened to 20-30 seconds. The default should be 20 seconds.

## Time Handling

The Web UI accepts and displays times in Beijing time. Backend parsing should normalize task input with the same Beijing-time semantics used by the match list and paper recommendation pages.

Database storage may continue using the project's existing datetime conventions, but every user-facing automation timestamp must be formatted as Beijing time:

- task trigger time
- target match window
- task created/updated/started/finished/missed/cancelled times
- Bark notification times
- task detail and error timestamps

## Creation Rules

`POST /api/paper-automation/tasks` accepts:

```json
{
  "trigger_at": "2026-06-15T18:21",
  "match_window_start": "2026-06-15T18:30",
  "match_window_end": "2026-06-15T18:30"
}
```

Validation:

- `trigger_at` must be in the future.
- `match_window_end >= match_window_start`.
- The local database must already contain at least one match with kickoff in the target window. If not, reject the task and instruct the user to pull/confirm fixtures first.
- Reject or clearly report duplicate pending/running tasks with the same `trigger_at`, `match_window_start`, and `match_window_end`.
- Bark configuration is not required for task creation. If missing, return a warning and later store `notification_status = not_configured`.

The target match set is selected only by kickoff time window. It does not inherit current match-list league/search/status filters.

## Scheduler

The Web backend starts a lightweight poller when the app starts.

Each poll:

1. If any task is `running`, do not start another task.
2. Find the earliest `pending` task by `trigger_at`.
3. If `now < trigger_at`, do nothing.
4. If `now > trigger_at + grace_minutes`, mark the task `missed`.
5. Otherwise claim the task as `running` in a database transaction.
6. Execute the fixed workflow.
7. Store `success` or `failed`, `finished_at`, and `result_payload`.
8. Send Bark and store notification status separately.

The `pending -> running` claim must be transactionally guarded so the task cannot be started twice if the app is restarted or the poller overlaps.

Tasks are globally serial in v1. If a later task waits behind a running task and then exceeds its grace window, mark it `missed`.

## Execution Workflow

For each task:

1. Select target matches by kickoff window.
2. Run odds backfill/sync for those matches.
3. Build the paper recommendation queue for the same window.
4. Create paper recommendation records for rows with `status == "candidate"`.
5. Rebuild the paper tracking/confidence workspace from the updated paper records.
6. Format Bark notification from the same confidence groups shown in the Web paper recommendation record page.
7. Send Bark.
8. Store summaries and errors in `result_payload`.

### Partial Odds Failures

If the target window has multiple matches and one match fails odds backfill, the task should continue.

Example:

- Match A odds success
- Match B odds failed
- Match C odds success

The task should continue to candidate generation. The failed match will naturally appear as no odds/stale odds/diagnostic state if it cannot qualify. Store the per-match failure summary in `result_payload` and Bark.

Only systemic failures should mark the task `failed`, such as database failure, an unhandled sync exception, candidate generation exception, or batch recording exception.

### No Candidates

No candidates is a successful task outcome:

```text
status = success
created_records = 0
```

Bark must still send a completion receipt with the target window, odds summary, candidate count, record count, and diagnostic counts.

## Paper Record And Confidence Consistency

Paper records are still stored in `paper_recommendation_records`.

After creating records, rebuild the paper confidence workspace using the existing `build_paper_confidence_workspace(...)` logic. Bark recommendation lines must be built from the resulting confidence groups, not from a separate ad hoc score formula.

This is required so the phone notification and Web paper recommendation record page agree exactly on:

- recommendation grouping
- displayed recommendation text
- confidence score
- suggested stake units

The Bark detail set should include every confidence group affected by the task's newly created records. If multiple strategies for the same match/market/side are recorded, Bark should show the grouped recommendation once, the same way the Web record page groups it.

## Bark Message Format

Use concise Chinese text optimized for phone reading.

Success with records:

```text
纸面自动任务：已记录 3 条
窗口：18:30 - 18:30
回填：3场 成功3 失败0

1. 日职联 横滨水手 vs 神户胜利船
   18:30 客队 +0.50  评分80  推荐1.50手

2. 韩K 蔚山HD vs 首尔FC
   18:30 小 2.50  评分76  推荐1.00手
```

No candidates:

```text
纸面自动任务：无候选
窗口：18:30 - 18:30
回填：3场 成功2 失败1
候选：0 记录：0

诊断：no_odds=1 robustness_filtered=2
```

Task failure:

```text
纸面自动任务：失败
窗口：18:30 - 18:30
阶段：刷新候选
错误：feature csv not found ...
```

Do not drop recorded recommendations because a message is long. If needed, split into multiple Bark pushes:

```text
纸面自动任务：已记录 12 条（1/3）
纸面自动任务：已记录 12 条（2/3）
纸面自动任务：已记录 12 条（3/3）
```

Each part should include enough window/context text to be readable independently.

## API

Add:

```text
GET    /api/paper-automation/tasks
POST   /api/paper-automation/tasks
GET    /api/paper-automation/tasks/{id}
POST   /api/paper-automation/tasks/{id}/cancel
```

List response should support the automation page:

- task id
- trigger time
- target window
- status
- notification status
- target match count
- created record/group count
- updated time
- short error/summary

Detail response should include:

- full task fields
- odds summary
- queue diagnostics
- batch record result
- confidence groups included in Bark
- Bark title/body or message parts
- notification error
- task error

Cancel:

- Allowed only for `pending`.
- Reject `running`, `success`, `failed`, and `cancelled`.

## UI

### Match List Page

Add a lightweight `创建自动任务` entry point near existing match-list actions.

Dialog fields:

- `触发任务时间`
- `筛选比赛开始时间`
- `筛选比赛结束时间`

Do not add match preview, row selection, or new task columns to the match table.

On successful creation, show a concise message such as:

```text
自动任务已创建，将于 18:21 执行
```

If no local matches exist in the target window, show:

```text
该比赛时间段当前没有本地赛程，请先在比赛列表拉取/确认赛程后再创建自动任务
```

### Automation Task Page

Add a new navigation entry: `自动任务`.

The page is a compact operational table.

Top metrics:

- pending
- running
- completed today
- failed / Bark failed

Main table:

- trigger time
- match window
- status
- target match count
- created recommendation group count
- Bark status
- updated time
- actions

Actions:

- view details
- cancel pending task

Details:

- odds backfill summary
- candidate diagnostics
- batch record result
- confidence groups sent to Bark
- Bark message title/body or message parts
- task error
- notification error/status code

## Testing

Backend tests:

- Create task rejects empty local fixture window.
- Create task rejects past trigger time.
- Create task rejects duplicate pending/running task.
- Pending task runs when due.
- Due task missed after grace window.
- Multiple due tasks execute serially.
- Running task prevents another task from starting.
- A task delayed beyond grace while waiting becomes `missed`.
- Partial per-match odds failure does not fail the task.
- Candidate generation exception fails the task.
- No-candidate task succeeds and sends no-candidate Bark text.
- Duplicate paper records are skipped and reported.
- Bark failure leaves task `success` but notification `failed`.
- Bark not configured leaves task `success` but notification `not_configured`.
- Bark content includes all affected confidence groups and uses the same `confidence_score` and `suggested_stake_units` as `build_paper_confidence_workspace(...)`.
- Cancel only works for pending tasks.

Frontend tests:

- Match list creation dialog renders.
- Successful task creation shows the scheduled message.
- No-local-fixture validation error is shown.
- Automation task page lists statuses and Bark state.
- Pending tasks show cancel action.
- Running/success/failed tasks do not show cancel action.
- Detail view shows odds, record, confidence, and Bark errors.

## Rollout

Implement in small slices:

1. Data model, task repository/service, and tests.
2. Bark notifier and message formatter with confidence-group consistency tests.
3. Task execution service and scheduler.
4. Web API.
5. Match list creation dialog.
6. Automation task page.

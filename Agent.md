# Agent Guide

This document is for future Codex sessions working in this repository.

## Collaboration Style

- The user prefers Chinese communication, concise operational summaries, and direct execution when the next step is clear.
- Keep the user informed while running long checks or workers, but avoid excessive narration.
- Do not expose `.env` values or API keys.
- Do not stop active workers unless the user asks, or unless continuing would clearly damage data or waste requests.
- When showing any match, odds, worker, or report timestamp to the user, convert UTC database values to Beijing time.
- When showing league/team names to the user, use configured Chinese display names when available. Keep raw/source names only as secondary debug fields.
- When showing Asian handicap recommendations, spell out the playable side and handicap in user-facing language, e.g. `客队 +0.50`; do not rely only on internal labels such as `away_cover`.
- Asian handicap line is stored from the home-team perspective: `-0.50` means home gives 0.5 and away recommendation is `客队 +0.50`; `+0.25` means home receives 0.25 and away recommendation is `客队 -0.25`.
- Prefer exact local commands and file paths. The user shares the same workspace.

## Repo And Runtime

- Repo path: `D:\project\IcewinePredictionModel`
- Shell: PowerShell
- Python: `C:\ProgramData\anaconda3\python.exe`
- Common environment:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONIOENCODING='utf-8'
```

- Main local DB: `local_data/icewine_prediction.sqlite3`
- Odds logs: `logs\odds`
- Web console control script:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 start
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 stop
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 status
```

- The script manages backend `http://127.0.0.1:8000` and frontend `http://127.0.0.1:5173`. Direct `.\start_web.ps1 ...` may be blocked by local PowerShell execution policy; use the `-ExecutionPolicy Bypass -File` form when that happens.
- Runtime PID state is written to `.web/`, which is gitignored.
- Common worker status command:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 120
```

## Engineering Rules

- Use `rg` for search.
- Use `apply_patch` for manual file edits.
- Before committing, run focused tests for the touched area.
- Do not revert user changes.
- Keep commits focused and explain what was verified.
- Avoid adding temporary scripts to git unless they are deliberately productized.

## Current Web Console Baseline

- The Web console now opens on `比赛列表` by default.
- Sidebar is intentionally trimmed to: `比赛列表`, `中文名`, `模型训练`, `纸面跟踪`, `推荐记录`.
- Hidden pages/components/API for overview, coverage, unmatched, worker, Oddspapi audit, and standalone odds trend may still exist in code; they are not current navigation entry points.
- `推荐记录` is kept as a page, but local demo/formal recommendation records were cleared from `recommendation_records`. Do not confuse this with `paper_recommendation_records`, which remains in use.
- Match-list sync results are persisted as per-match `data_sync_run_items`. Use `GET /api/data-sync-runs/{run_id}/items` or the page's `最近同步诊断` panel when diagnosing failed odds/result syncs.
- Match detail includes a standard execution-timepoint coverage matrix for `T-60/T-30/T-25/T-20/T-15/T-10` across Asian handicap, total goals, and match winner. Existing cells are read-only; missing cells expose manual supplement buttons.
- Manual standard-timepoint odds supplement uses `POST /api/matches/{match_id}/execution-timepoint-odds/manual`. It writes to `historical_odds_snapshots` as `source_name=oddspapi`, `bookmaker=pinnacle`, with `market_id` prefixed by `manual-` and `raw_payload.source=manual`. It must not overwrite an already-covered standard timepoint; backend returns `already_exists`.
- `同步赛程/赛果` skips truly live/in-play matches in program logic and reports `比赛进行中，暂不申请赛果`; this is intentional to avoid mixing live scores with final results.
- API-Football client has lightweight pacing/retry defaults via `build_api_football_provider`: `0.8s` request cooldown, one retry, `2.0s` retry cooldown.

## Execution Timepoint Rules

- Standard T-n timepoints mean kickoff minus `n` minutes, with a shared tolerance of `±5` minutes from `execution_timepoint_service.DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES`.
- The current standard targets are `T-60/T-30/T-25/T-20/T-15/T-10`.
- Paper candidate generation uses the same historical snapshot source and timepoint concepts for scheduled and finished matches. Do not reintroduce separate "latest close only" logic for finished replay unless the user explicitly changes the design.
- Candidate decision pricing is T-10 oriented and may fall back through earlier available targets up to T-30. Robustness observations may use the broader target set including T-60.
- When diagnosing whether a match should enter paper candidates, inspect both the match detail coverage matrix and `build_paper_recommendation_queue` output; the matrix only proves odds availability, not that a strategy's robustness rule was met.

## OddsPapi Worker Defaults

Use safe mode for long unattended runs unless explicitly choosing otherwise:

```powershell
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-start `
  --season <season> `
  --mode safe `
  --chunk-size 4 `
  --request-budget-per-league 500 `
  --timeout-seconds 40 `
  --max-snapshots-per-match 151 `
  --max-rounds-per-league 300 `
  --stop-after-empty-matches 8 `
  --stop-after-failed-rounds 2 `
  --round-timeout-seconds 500.0 `
  --historical-odds-cooldown-seconds 7.5 `
  --hard-timeout-seconds 28800.0 `
  --log-dir logs\odds `
  --league-ids <ids> `
  --from-date 2026-01-15 `
  --notify-on-complete
```

`odds audit` is local DB/log based and does not call Oddspapi. Probe, fixture diagnosis, fetch, and worker commands do call Oddspapi.

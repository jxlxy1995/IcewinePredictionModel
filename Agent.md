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

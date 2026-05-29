# Current Context

Last updated: 2026-05-29, Asia/Shanghai.

## Current Git State

There are local uncommitted changes from removing 德丙 from the whitelist:

- `config/leagues.yaml`
- `tests/test_settings.py`

The DB was also updated locally:

- `leagues.source_league_id='80'` is now `is_enabled=0`.

Focused test run after this change:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_settings.py -q
```

Result: `3 passed`.

Next session should decide whether to commit this small change.

## Current Odds Coverage Snapshot

Using finished matches after `2026-01-15` as denominator, before removing 德丙:

- Eligible matches: `5943`
- Successful odds matches: `4970`
- Coverage: `83.6%`
- Full three-market matches: `4970`
- empty: `444`
- none: `428`
- unmatched: `0` after cleanup
- unavailable: increased by 4 after cleanup
- failed: `0`

After disabling 德丙 locally, enabled eligible total is `5753`.

Leagues still completely unrunned or intentionally pending:

- 欧冠
- 欧联
- 欧协联

德丙 should no longer be treated as a target whitelist league.

## Last Completed Work

1. Ran full local odds audit for 2025/2026.
2. Committed backfill tooling and alias improvements in `89efda1`.
3. Rechecked the four remaining unmatched matches:
   - `4652` 西乙 Sporting Gijon vs Leganes
   - `5501` 法乙 Bastia vs Le Mans
   - `6502` 荷乙 Cambuur vs Vitesse
   - `15939` 瑞典超甲 GIF Sundsvall vs United Nordic
4. All four still failed fixture matching after targeted retry, so they were marked `unavailable`.
5. Removed 德丙 from `config/leagues.yaml` and adjusted `tests/test_settings.py`, not yet committed.

## Likely Next Work

The user is considering adding more leagues to expand sample size:

- 爱超, Ireland
- 芬甲, Finland second tier
- 挪甲, Norway second tier
- 丹麦甲, Denmark second tier

Recommended approach:

1. Do not add them directly to the main whitelist yet.
2. Identify API-Football league IDs and check whether local match history exists.
3. Add display names only after deciding to test.
4. Generate 8 no-repeated-team sample candidates per league if possible.
5. Run small Oddspapi sample backfill.
6. If fixture matching and odds coverage look good, add the league to `config/leagues.yaml` and mapping tables.

Suggested priority:

1. 挪甲
2. 芬甲
3. 丹麦甲
4. 爱超

## Useful Commands

Run local odds audit:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-audit-backfill --season 2026 --log-dir logs\odds --top-errors 10
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-audit-backfill --season 2025 --log-dir logs\odds --top-errors 10
```

Check worker:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 120
```

Generate sample candidates:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-sample-candidates --season 2026 --league-ids <ids> --from-date 2026-01-15 --per-league 8
```


# Current Context

Last updated: 2026-05-29, Asia/Shanghai.

## Current Git State

The whitelist/reminder-doc change has been committed:

- Commit `bed3ed9 移除德丙白名单并新增接力文档`
- Included `config/leagues.yaml`, `tests/test_settings.py`, `Agent.md`, `memory.md`, and `Context.md`

The DB was also updated locally:

- `leagues.source_league_id='80'` is now `is_enabled=0`.

Focused test run before commit:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_settings.py -q
```

Result: `3 passed`.

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
5. Removed 德丙 from `config/leagues.yaml` and adjusted `tests/test_settings.py`.
6. Committed the 德丙 whitelist removal and relay docs in `bed3ed9`.
7. Ran a read-only candidate-league precheck using official API-Football metadata, API-Football fixtures, and OddsPapi `tournaments`/`fixtures`. This did not write to DB and did not fetch historical odds.
8. Synced API-Football fixture/results history for the five candidate leagues only. This pulled schedule/result data, not odds:
   - 爱超 `357`, season `2026`: `created=180`
   - 芬甲二级 `1087` Ykkösliiga, season `2026`: `created=135`
   - 挪甲 `104`, season `2026`: `created=240`
   - 丹麦甲 `120`, season `2025`: `created=192`
   - 印尼超 `274`, season `2025`: `created=306`
9. After syncing, these five candidate leagues were set to `is_enabled=0` in the local DB so they remain candidates and do not affect enabled-league coverage until deliberately promoted.

## Likely Next Work

The user is considering adding more leagues to expand sample size:

- 爱超, Ireland
- 芬甲, Finland second tier
- 挪甲, Norway second tier
- 丹麦甲, Denmark second tier
- 印尼超, Indonesia top tier

Read-only candidate IDs found on 2026-05-29:

| 中文 | API-Football | API season | OddsPapi tournament | Notes |
| --- | ---: | ---: | ---: | --- |
| 爱超 | `357` Premier Division | `2026` | `192` Premier Division, Ireland | 2026 current season |
| 芬甲二级 | `1087` Ykkösliiga | `2026` | `55` Ykkosliiga, Finland | This is the better fit for "Finland second tier" |
| 芬甲/API旧名 | `245` Ykkönen | `2026` | `42291` Ykkonen, Finland | Now appears separate from second-tier Ykkösliiga |
| 挪甲 | `104` 1. Division | `2026` | `22` 1st Division, Norway | 2026 current season |
| 丹麦甲 | `120` 1. Division | `2025` | `47` 1. Division, Denmark | Current season is API-Football `2025` |
| 印尼超 | `274` Liga 1 | `2025` | `1015` Liga 1, Indonesia | Current season is API-Football `2025` |

Read-only fixture prediagnostic result:

| 中文 | Finished after 2026-01-15 | No-repeat sample | Fixture match result |
| --- | ---: | ---: | --- |
| 爱超 | `91` | `5` | `4 matched`, `1 OddsPapi 404` |
| 芬甲二级 | `40` | `4` | `2 matched`, `2 miss`, likely needs aliases |
| 挪甲 | `71` | `8` | `4 matched`, `4 miss`, likely needs aliases |
| 丹麦甲 | `78` | `6` | `3 matched`, `1 weak`, `1 miss`, `1 OddsPapi 404` |
| 印尼超 | `153` | `8` | `5 matched`, `2 weak`, `1 OddsPapi 404` |

Local DB snapshot after candidate history sync:

| 中文 | DB source id | 2026 total | 2026 finished | DB enabled |
| --- | ---: | ---: | ---: | ---: |
| 爱超 | `357` | `180` | `91` | `0` |
| 芬甲二级 | `1087` | `135` | `40` | `0` |
| 挪甲 | `104` | `240` | `71` | `0` |
| 丹麦甲 | `120` | `84` | `78` | `0` |
| 印尼超 | `274` | `171` | `171` | `0` |

芬甲二级人工校对样本, all `Group Stage`, not playoff/promotion/relegation-looking:

- `17537` API `1504193`, `2026-04-04 00:00` BJT, PK-35 4-2 EIF
- `17538` API `1504194`, `2026-04-06 21:00` BJT, JIPPO 0-0 JäPS
- `17539` API `1504195`, `2026-04-06 21:00` BJT, Klubi-04 1-2 KäPa
- `17540` API `1504196`, `2026-04-06 21:00` BJT, SJK Akatemia 1-0 MP
- `17541` API `1504197`, `2026-04-10 23:30` BJT, JäPS 1-0 Klubi-04
- `17542` API `1504198`, `2026-04-10 23:30` BJT, Kooteepee 1-0 MP
- `17543` API `1504199`, `2026-04-11 00:00` BJT, KäPa 2-2 SJK Akatemia
- `17545` API `1504201`, `2026-04-11 23:00` BJT, PK-35 0-0 Haka

Observed alias needs before any real backfill:

- 印尼超: `Pusamania Borneo -> Borneo Samarinda`, `Persepam Madura Utd -> Madura United`, `PSBS Biak Numfor -> PSBS Biak`.
- 丹麦甲: `HB Koge -> HB Koege`, `B 93` may need manual alias/normalization check.
- 挪甲: `Stromsgodset`, `ODD Ballklubb`, `hodd`, `Strommen`, and possibly `Sogndal`/`Sandnes ULF` need alias review.
- 芬甲二级: `PK-35`, `EIF`, `SJK Akatemia`, `MP` need alias review.

Recommended approach:

1. Do not add them directly to the main whitelist yet.
2. If proceeding, first add temporary/real tournament mappings and aliases for the sample leagues.
3. Sync local API-Football history only for the selected candidates.
4. Generate sample candidates from local DB.
5. Run small OddsPapi historical-odds backfill or targeted `match_ids` fetch for matched samples.
6. If fixture matching and three-market odds coverage look good, add the league to `config/leagues.yaml`, display names, mapping tables, and alias data.

Suggested priority:

1. 爱超: best fixture match quality, but only 5 no-repeat teams in the first-pass sample.
2. 印尼超: largest sample and good matching after obvious aliases.
3. 丹麦甲: usable, moderate alias needs.
4. 挪甲: enough sample size, but more alias misses.
5. 芬甲二级: real second-tier candidate, but small sample and alias misses.

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

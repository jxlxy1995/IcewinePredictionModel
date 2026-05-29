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
7. Ran a read-only precheck for five new main leagues using official API-Football metadata, API-Football fixtures, and OddsPapi `tournaments`/`fixtures`. This did not write to DB and did not fetch historical odds.
8. Synced API-Football fixture/results history for the five new main leagues only. This pulled schedule/result data, not odds:
   - 爱超 `357`, season `2026`: `created=180`
   - 芬甲二级 `1087` Ykkösliiga, season `2026`: `created=135`
   - 挪甲 `104`, season `2026`: `created=240`
   - 丹麦甲 `120`, season `2025`: `created=192`
   - 印尼超 `274`, season `2025`: `created=306`
9. These five leagues were initially kept disabled while they were being validated, but they are now treated as regular main leagues.
10. Added OddsPapi tournament mappings for the five new main leagues in `9f51cd0`:
   - `357 -> 192` 爱超
   - `1087 -> 55` 芬甲/Ykkösliiga
   - `104 -> 22` 挪甲
   - `120 -> 47` 丹麦甲
   - `274 -> 1015` 印尼超
11. Ran a small OddsPapi historical-odds sample backfill, 3 matches per new main league. Final result after alias retry:
   - 挪甲: `3/3` success
   - 芬甲: `2/3` success, `1` unavailable 404 (`17572` SJK Akatemia vs Haka)
   - 丹麦甲: `1/3` success, `1` unavailable 404 (`18040` Kolding IF vs B 93), `1` unmatched (`18041` Hillerød vs Aarhus Fremad)
   - 印尼超: `3/3` success
   - 爱超: `2/3` success, `1` unavailable 404 (`17471` Bohemians vs Shamrock Rovers)
12. Added alias fixes that turned 3 unmatched samples into successful backfills:
   - `hodd -> Hoedd IL`
   - `Strommen -> Stroemmen IF`
   - `EIF -> Ekenas Idrottsforening`
13. Ran the first larger 2026 worker for 挪甲/芬甲/爱超. Worker completed:
   - Total: processed `142`, snapshots `20072`, failed `35`, requests `292`.
   - 挪甲: finished `71`, success/snapshot matches `46` before post-fix, then `47` after targeted alias retry; remaining `unknown=13`, `unavailable=10`.
   - 芬甲: finished `40`, success `18` before post-fix, then `20` after targeted alias retry; remaining `unknown=11`, `unavailable=9`.
   - 爱超: finished `91`, success `84`, unavailable `6`, empty `1`. This league looks healthy enough for future continuation.
14. Post-worker alias repair added:
   - `ODD Ballklubb -> Odds BK`
   - `Stromsgodset -> Stroemsgodset IF`
   - `Kooteepee -> FC KTP Kotka`
   - `MP -> Mikkelin Palloilijat`
   Targeted retry of `17737,17733,17575,17571` produced 3 successes and 1 real 404 (`17737` ODD Ballklubb vs Ranheim).

## Likely Next Work

2026-05-29 later update:

- The five new leagues are now regular main leagues, not candidate leagues.
- Odds backfill for these five main leagues is effectively complete for the current finished-match window.
- Current new main league status:
  - Ireland Premier Division `357`: success `84`, unavailable `6`, empty `1`.
  - Finland Ykkosliiga `1087`: success `29`, unavailable `11`.
  - Norway 1. Division `104`: success `61`, unavailable `10`.
  - Denmark 1. Division `120`: success `69`, unavailable `9`.
  - Indonesia Liga 1 `274`: success `117`, empty `11`, unavailable `25`.
- Remaining failures are no longer alias backlog. They are OddsPapi 404/unavailable, empty usable main-line snapshots, or fixture candidates that clearly do not match the API-Football target match.
- Added Denmark 1. Division OddsPapi team aliases:
  - `Hillerød -> Hillerod Fodbold`
  - `B 93 -> B93 Copenhagen`
  - `HB Koge -> HB Koege`
- The user completed another pass of Chinese team display names in `config/display_names.yaml`.
- UEFA competitions: refreshed API-Football results only for 2025 season; no OddsPapi odds backfill.
  - UEFA Champions League `2`: total `281`, finished `280`, one future/not-finished final on `2026-05-31`.
  - UEFA Europa League `3`: total/finished `271`.
  - UEFA Europa Conference League `848`: total/finished `409`.
- Current direction: do not backfill UEFA odds yet. Keep UEFA results as auxiliary future context, not as the main training sample.

Recommended next step:

1. Freeze and commit display names plus Denmark alias repair.
2. Keep the five new leagues enabled in config and DB as regular main leagues.
3. Build a training dataset/audit report that separates main enabled leagues and UEFA auxiliary results.
4. Run a first model-training baseline using only settled matches with complete three-market OddsPapi snapshots.

The following five leagues have been added to the regular main-league set:

- 爱超, Ireland
- 芬甲, Finland second tier
- 挪甲, Norway second tier
- 丹麦甲, Denmark second tier
- 印尼超, Indonesia top tier

Read-only IDs found on 2026-05-29:

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

Local DB snapshot after history sync:

| 中文 | DB source id | 2026 total | 2026 finished | DB enabled |
| --- | ---: | ---: | ---: | ---: |
| 爱超 | `357` | `180` | `91` | `1` |
| 芬甲 | `1087` | `135` | `40` | `1` |
| 挪甲 | `104` | `240` | `71` | `1` |
| 丹麦甲 | `120` | `84` | `78` | `1` |
| 印尼超 | `274` | `171` | `171` | `1` |

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
- 挪甲: `hodd`, `Strommen`, `Stromsgodset`, and `ODD Ballklubb` are now fixed in config. `Sogndal`/`Sandnes ULF` may still need alias review.
- 芬甲: `EIF`, `Kooteepee`, and `MP` are now fixed in config. `SJK Akatemia` and possible future `KäPa` variants may still need alias review.

Current modeling direction:

1. Treat 爱超, 芬甲, 挪甲, 丹麦甲, and 印尼超 exactly like the other enabled main leagues.
2. Do not backfill UEFA odds yet; keep UEFA results as auxiliary future context.
3. Next major task is a full main-league training data audit using enabled leagues only.

Main-league training data audit completed:

- Report: `docs/团队协作/20260529-main-league-training-data-audit.md`
- Scope: enabled main leagues, UEFA excluded from odds sample, `kickoff_time >= 2026-01-15`.
- Eligible main-league matches: `5981`.
- Complete three-market OddsPapi/Pinnacle matches: `5330` (`89.1%`).
- Status split: success `5330`, empty `456`, unavailable `95`, none `100`, unmatched `0`, failed `0`.
- New five main leagues contribute `360` complete three-market matches from `433` eligible matches (`83.1%`).
- Low coverage under 80%: Ykkosliiga `72.5%`, Liga 1 Indonesia `76.5%`, Eerste Divisie `76.8%`.
- Recommended next step: build the baseline training dataset from complete three-market main-league matches.

Baseline training dataset v1 completed:

- Generator command: `icewine samples baseline-dataset`.
- Local CSV output: `local_data/training/baseline_main_leagues_20260529.csv` (gitignored local data).
- Report: `docs/团队协作/20260529-baseline-training-dataset.md`.
- Scope matches the main-league audit: enabled main leagues, UEFA excluded, finished/scored, `kickoff_time >= 2026-01-15` using the DB wall-time boundary.
- Rows: `5330` complete three-market matches from `5981` eligible main-league matches; coverage `0.8912`.
- CSV has `42` columns and includes match metadata, scores, result labels, close-line odds/probabilities/overrounds for `asian_handicap`, `total_goals`, and `match_winner`.
- Boundary note: a Saudi match at DB kickoff `2026-01-14 22:45:00` is intentionally excluded to stay aligned with the audit's literal DB timestamp window.

Baseline training dataset QA completed:

- QA command: `icewine samples baseline-dataset-qa`.
- QA report: `docs/团队协作/20260529-baseline-training-dataset-qa.md`.
- Rows/columns: `5330` rows, `42` columns.
- Validation issues: empty required cells `0`, invalid odds cells `0`, invalid probability cells `0`, invalid overround cells `0`.
- Thin-history rows: `152` (`0.0285`).
- Overround ranges: asian handicap `1.0090-1.0786`, total goals `1.0140-1.0922`, match winner `1.0171-1.1057`.
- Match results: home win `2325`, draw `1404`, away win `1601`.
- Low sample leagues under 30 rows: Ykkosliiga `29`.
- Recommended next step: close-market baseline evaluation on this CSV.

Close-market baseline evaluation completed:

- Command: `icewine samples baseline-market-baseline`.
- Report: `docs/团队协作/20260529-close-market-baseline-evaluation.md`.
- Evaluated market samples: `15326` of `15990`; skipped `664` mostly due binary-market push settlement.
- Asian handicap: evaluated `4928`, skipped `402`, accuracy `0.5244`, log loss `0.6921`, brier `0.4412`, avg overround `1.0273`, max-probability flat ROI `-0.0188`.
- Total goals: evaluated `5068`, skipped `262`, accuracy `0.5199`, log loss `0.6924`, brier `0.4474`, avg overround `1.0320`, max-probability flat ROI `-0.0220`.
- Match winner: evaluated `5330`, skipped `0`, accuracy `0.5032`, log loss `1.0055`, brier `0.6015`, avg overround `1.0390`, max-probability flat ROI `-0.0357`.
- This looks like a sane market baseline: all simple max-probability flat-bet ROIs are negative and broadly track market overround.
- Recommended next step: build first model feature set and compare validation metrics against this close-market baseline.

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

# Current Context

Last updated: 2026-05-29, Asia/Shanghai.

## Display Rules For Future Agents

- User-facing times for matches, odds, reports, workers, and logs should be shown in Beijing time.
- User-facing league/team names should use configured Chinese display names when mappings exist. Raw/source names may be included only as secondary debug context.
- User-facing Asian handicap recommendations must include the explicit playable side and handicap, such as `客队 +0.50` or `主队 -0.25`; internal labels like `away_cover` are debug context only.
- Asian handicap line is stored from the home-team perspective: `-0.50` means home gives 0.5 and away recommendation is `客队 +0.50`; `+0.25` means home receives 0.25 and away recommendation is `客队 -0.25`.

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

- Report: `docs/数据审计/20260529-main-league-training-data-audit.md`
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
- Report: `docs/数据审计/20260529-baseline-training-dataset.md`.
- Scope matches the main-league audit: enabled main leagues, UEFA excluded, finished/scored, `kickoff_time >= 2026-01-15` using the DB wall-time boundary.
- Rows: `5330` complete three-market matches from `5981` eligible main-league matches; coverage `0.8912`.
- CSV has `42` columns and includes match metadata, scores, result labels, close-line odds/probabilities/overrounds for `asian_handicap`, `total_goals`, and `match_winner`.
- Boundary note: a Saudi match at DB kickoff `2026-01-14 22:45:00` is intentionally excluded to stay aligned with the audit's literal DB timestamp window.

Baseline training dataset QA completed:

- QA command: `icewine samples baseline-dataset-qa`.
- QA report: `docs/数据审计/20260529-baseline-training-dataset-qa.md`.
- Rows/columns: `5330` rows, `42` columns.
- Validation issues: empty required cells `0`, invalid odds cells `0`, invalid probability cells `0`, invalid overround cells `0`.
- Thin-history rows: `152` (`0.0285`).
- Overround ranges: asian handicap `1.0090-1.0786`, total goals `1.0140-1.0922`, match winner `1.0171-1.1057`.
- Match results: home win `2325`, draw `1404`, away win `1601`.
- Low sample leagues under 30 rows: Ykkosliiga `29`.
- Recommended next step: close-market baseline evaluation on this CSV.

Close-market baseline evaluation completed:

- Command: `icewine samples baseline-market-baseline`.
- Report: `docs/模型实验/20260529-close-market-baseline-evaluation.md`.
- Evaluated market samples: `15326` of `15990`; skipped `664` mostly due binary-market push settlement.
- Asian handicap: evaluated `4928`, skipped `402`, accuracy `0.5244`, log loss `0.6921`, brier `0.4412`, avg overround `1.0273`, max-probability flat ROI `-0.0188`.
- Total goals: evaluated `5068`, skipped `262`, accuracy `0.5199`, log loss `0.6924`, brier `0.4474`, avg overround `1.0320`, max-probability flat ROI `-0.0220`.
- Match winner: evaluated `5330`, skipped `0`, accuracy `0.5032`, log loss `1.0055`, brier `0.6015`, avg overround `1.0390`, max-probability flat ROI `-0.0357`.
- This looks like a sane market baseline: all simple max-probability flat-bet ROIs are negative and broadly track market overround.
- Recommended next step: build first model feature set and compare validation metrics against this close-market baseline.

Web training workspace v1 completed:

- The Web console "模型训练" page is now a real training workflow workspace instead of only a static model overview.
- Backend endpoints added:
  - `GET /api/training/workspace`
  - `POST /api/training/baseline-dataset`
  - `POST /api/training/baseline-dataset-qa`
  - `POST /api/training/market-baseline`
- The backend still delegates business logic to the existing Python services/CLI layer and returns refreshed workspace status after each action.
- Frontend now shows baseline dataset status, QA status, close-market baseline metrics, report paths, and workflow buttons for generating the dataset, running QA, and running the market baseline.
- The model training page still keeps existing model-run and league-coverage panels below the new workflow panels.
- Verification run for this work:
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q` -> `14 passed`
  - `npm test -- modelTrainingWorkspace.test.ts` from `web` -> `5 passed`
  - `npm run build` from `web` -> passed
- `npm install` was run in `web` to restore local frontend dev dependencies; npm reported 5 moderate vulnerabilities, but no package manifest/lockfile diff was produced.

Baseline feature set v1 completed:

- CLI command: `icewine samples baseline-feature-set`.
- Service: `src/icewine_prediction/baseline_feature_set_service.py`.
- Local feature CSV output: `local_data/training/baseline_features_main_leagues_20260529.csv` (local data, not committed).
- Report: `docs/数据审计/20260529-baseline-feature-set-v1.md`.
- Input: `local_data/training/baseline_main_leagues_20260529.csv`.
- Rows: `5330`; train rows `4262`; validation rows `1068`.
- Split: time-ordered, validation ratio target `0.2000`, with identical kickoff times kept in the same split.
- Train window: `2026-01-17T14:00:00` to `2026-05-03T07:15:00`.
- Validation window: `2026-05-03T07:30:00` to `2026-05-28T00:00:00`.
- Zero-history rows: `421`.
- Feature rows use only prior same-league team history before each kickoff: rolling matches, points/match, W/D/L rates, goals for/against, venue-specific prior points, rest days, close lines, and close implied probabilities/overrounds.
- Focused verification:
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_baseline_feature_set_service.py -q` -> `4 passed`
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_samples_cli.py -q` -> `21 passed`

Baseline match-winner model v1 completed:

- CLI command: `icewine samples baseline-match-winner-model`.
- Service: `src/icewine_prediction/baseline_match_winner_model_service.py`.
- Report: `docs/模型实验/20260529-baseline-match-winner-model-v1.md`.
- Input: `local_data/training/baseline_features_main_leagues_20260529.csv`.
- Model type: scikit-learn `LogisticRegression` with median imputation, standard scaling, balanced class weights, `max_iter=1000`, `random_state=42`.
- Three model variants:
  - `team_form_only`: 20 rolling same-league team-history features.
  - `team_form_plus_market`: team-history features plus match-winner close implied probabilities/overround, 24 features.
  - `team_form_plus_all_markets`: team-history features plus match-winner, Asian handicap, and total-goals close line/probability/overround features, 32 features.
- Validation rows: `1068` from the feature-set v1 time split.
- Close-market match-winner reference is now recomputed on the same validation split: evaluated `1068`, accuracy `0.5009`, log loss `1.3146`, brier `0.6071`.
- Validation close-market predicted result distribution: home win `737`, draw `2`, away win `329`.
- Results:
  - `team_form_only`: accuracy `0.3811`, log loss `1.1378`, brier `0.6582`.
  - `team_form_plus_market`: accuracy `0.4579`, log loss `1.3126`, brier `0.6275`.
  - `team_form_plus_all_markets`: accuracy `0.4466`, log loss `1.3155`, brier `0.6285`.
- Initial read: `team_form_plus_market` is roughly tied with same-split close market on log loss, trails it on accuracy/Brier, and predicts many more draws; adding Asian handicap and total-goals market features did not improve the match-winner proxy task. These markets may still be useful for the actual Asian handicap / total-goals targets rather than for胜平负.
- Calibration buckets were added to the match-winner model report:
  - close market: confidence buckets are broadly monotonic; 0.80-0.90 bucket has `13` samples, avg confidence `0.8306`, accuracy `0.9231`.
  - `team_form_only`: `798/1068` validation rows sit in 0.30-0.40 confidence with avg confidence `0.3679`, accuracy `0.3283`; low confidence concentration explains the low accuracy despite better log loss.
  - `team_form_plus_market`: calibration is broadly monotonic and close-market-like; 0.60-0.70 bucket has avg confidence `0.6449`, accuracy `0.6907`.
  - `team_form_plus_all_markets`: calibration remains broadly monotonic, but metrics are slightly worse than `team_form_plus_market`.
- Focused verification:
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_baseline_match_winner_model_service.py -q` -> `2 passed`
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_baseline_match_winner_model_service.py tests/test_samples_cli.py tests/test_baseline_feature_set_service.py -q` -> `29 passed`
  - `C:\ProgramData\anaconda3\python.exe -m pytest tests/test_samples_cli.py tests/test_baseline_match_winner_model_service.py -q` -> `25 passed`

Baseline Asian handicap model v1 completed:

- Feature set v1 now carries Asian handicap target/result and odds fields:
  - `target_asian_handicap_home_result`
  - `target_asian_handicap_away_result`
  - `asian_handicap_home_odds`
  - `asian_handicap_away_odds`
- CLI command: `icewine samples baseline-asian-handicap-model`.
- Service: `src/icewine_prediction/baseline_asian_handicap_model_service.py`.
- Report: `docs/模型实验/20260529-baseline-asian-handicap-model-v1.md`.
- Input: `local_data/training/baseline_features_main_leagues_20260529.csv`.
- Scope: binary Asian handicap direction only; rows with push/half-win/half-loss or non-clear settlement are skipped for v1.
- Rows: `5330`; train rows `3317`; validation rows `853`; skipped rows `1160`.
- Same-split close-market reference: evaluated `853`, accuracy `0.5287`, log loss `0.6971`, brier `0.4978`.
- Results:
  - `team_form_plus_match_winner_market`: accuracy `0.5064`, log loss `0.6965`, brier `0.4996`.
  - `team_form_plus_all_markets`: accuracy `0.5334`, log loss `0.6993`, brier `0.4990`.
- Initial read: full-market features improve directional accuracy versus close market, but log loss/Brier do not clearly beat market. All confidence is concentrated around 0.50-0.60, which confirms Asian handicap v1 is a thin-edge, near-coinflip task.

Baseline total-goals model v1 completed:

- Feature set v1 now also carries total-goals target/result and odds fields:
  - `target_total_goals_over_result`
  - `target_total_goals_under_result`
  - `total_goals_over_odds`
  - `total_goals_under_odds`
- CLI command: `icewine samples baseline-total-goals-model`.
- Service: `src/icewine_prediction/baseline_total_goals_model_service.py`.
- Report: `docs/模型实验/20260529-baseline-total-goals-model-v1.md`.
- Input: `local_data/training/baseline_features_main_leagues_20260529.csv`.
- Scope: binary total-goals direction only; rows with push/half-win/half-loss or non-clear settlement are skipped for v1.
- Rows: `5330`; train rows `3476`; validation rows `891`; skipped rows `963`.
- Same-split close-market reference: evaluated `891`, accuracy `0.5174`, log loss `0.6927`, brier `0.4996`.
- Results:
  - `team_form_plus_match_winner_market`: accuracy `0.4871`, log loss `0.6970`, brier `0.5039`.
  - `team_form_plus_all_markets`: accuracy `0.4994`, log loss `0.6991`, brier `0.5059`.
- Initial read: total-goals v1 does not beat the same-split close market on accuracy, log loss, or Brier. The model leans under-heavy and confidence remains mostly 0.50-0.60, so the current feature set is not recommendation-ready for totals.

Baseline market diagnostics v1 completed:

- CLI command: `icewine samples baseline-market-diagnostics`.
- Service: `src/icewine_prediction/baseline_market_diagnostics_service.py`.
- Report: `docs/数据审计/20260529-baseline-market-diagnostics-v1.md`.
- Input: `local_data/training/baseline_features_main_leagues_20260529.csv`.
- Scope: validation split only, close-market implied-probability direction, binary clear-settlement rows only.
- Rows: `5330`; validation rows `1068`.
- Asian handicap diagnostics:
  - Eligible rows `853`; skipped rows `215`; close-market accuracy `0.5287`.
  - Actual side distribution is almost balanced: away cover `427`, home cover `426`.
  - Market predicted home cover more often than actual: predicted home cover `468`, away cover `385`.
  - By actual side: home cover accuracy `0.5775`, away cover accuracy `0.4801`.
  - By line, stronger sample-size segments include `-0.50` accuracy `0.5833`, `0.25` accuracy `0.6000`, `-1.00` accuracy `0.5862`; weak segments include `-0.75` accuracy `0.4667`, `-1.50` accuracy `0.3913`, `1.00` accuracy `0.1333` with only `15` rows.
- Total-goals diagnostics:
  - Eligible rows `891`; skipped rows `177`; close-market accuracy `0.5174`.
  - Actual side distribution is also balanced: over `449`, under `442`.
  - Market confidence buckets are all `0.50-0.60` for both Asian handicap and total goals, so close-market confidence does not provide useful segmentation yet.
  - By actual side: over accuracy `0.5345`, under accuracy `0.5000`.
  - By line, larger sample-size segments are mostly close to coinflip: `2.50` accuracy `0.5060`, `2.75` accuracy `0.5188`, `3.00` accuracy `0.5469`, `2.25` accuracy `0.5221`; `3.50` is better at `0.6061` over `66` rows.
- Initial read: diagnostics reinforce that current close-market labels are thin-edge and balanced. The next useful modeling step is likely adding richer pre-match dynamics/features, not simply slicing by market confidence.

Historical odds anchor coverage v1 completed:

- CLI command: `icewine samples historical-odds-anchor-coverage`.
- Service: `src/icewine_prediction/historical_odds_anchor_coverage_service.py`.
- Report: `docs/数据审计/20260529-historical-odds-anchor-coverage-v1.md`.
- Scope: all finished/scored matches after `2026-01-15` Beijing time, no season filter, bookmaker `pinnacle`, core markets `asian_handicap` and `total_goals`.
- Eligible matches: `6377`.
- Both Asian handicap and total goals:
  - Samples: `5330`; sample coverage vs eligible matches `0.8358`.
  - Complete core-anchor samples (`24h`, `12h`, `6h`, `3h`, `1h`, `close`): `5109`; eligible coverage `0.8012`.
  - Average snapshots: Asian handicap `48.84`, total goals `48.81`.
  - Anchor coverage inside the `5330` available samples:
    - `24h`: `5109`, sample coverage `0.9585`.
    - `12h`: `5175`, sample coverage `0.9709`.
    - `6h`: `5330`, sample coverage `1.0000`.
    - `3h`: `5330`, sample coverage `1.0000`.
    - `1h`: `5330`, sample coverage `1.0000`.
    - `close`: `5330`, sample coverage `1.0000`.
- Initial read: dynamic market features are viable. A v1 feature set can safely use `6h`, `3h`, `1h`, and `close`; `24h`/`12h` are also strong enough if missing values are imputed or if a complete-core subset is used for comparison.

Baseline dynamic feature set v1 completed:

- CLI command: `icewine samples baseline-dynamic-feature-set`.
- Service: `src/icewine_prediction/baseline_dynamic_feature_set_service.py`.
- Input: `local_data/training/baseline_features_main_leagues_20260529.csv`.
- Output: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv` (local generated data, not committed).
- Report: `docs/数据审计/20260529-baseline-dynamic-feature-set-v1.md`.
- Rows: `5330`.
- Rows with Asian handicap dynamic features: `5330`.
- Rows with total-goals dynamic features: `5330`.
- Complete core-anchor rows (`6h`, `3h`, `1h`, `close` for both Asian handicap and total goals): `5330`.
- Dynamic CSV has `166` unique columns. Close-anchor dynamic fields are named with `close_anchor` (for example `asian_handicap_close_anchor_line`) to avoid colliding with existing static close fields.
- Feature families added for both `asian_handicap` and `total_goals`:
  - Anchor line, odds, implied probabilities, and overround for `24h`, `12h`, `6h`, `3h`, `1h`, and `close_anchor`.
  - Anchor-to-close line movement and side probability movement.
  - Snapshot count and missing anchor labels.
- Initial read: the dynamic feature set is ready for the next modeling pass. Use the generated dynamic CSV as the model input and compare static-only vs static+dynamic variants for Asian handicap and total goals.

Dynamic market model comparison v1 completed:

- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Reports:
  - `docs/模型实验/20260529-baseline-asian-handicap-dynamic-model-v1.md`.
  - `docs/模型实验/20260529-baseline-total-goals-dynamic-model-v1.md`.
- Code now automatically adds dynamic model variants when the input CSV contains the dynamic core anchor columns:
  - Market-specific dynamic core: `6h`, `3h`, `1h`, `close_anchor`.
  - All dynamic core: both Asian handicap and total goals dynamic core columns.
- Asian handicap validation:
  - Rows `5330`; train `3317`; validation `853`; skipped `1160`.
  - Close-market reference: accuracy `0.5287`, log loss `0.6971`, brier `0.4978`.
  - Static all-market model: accuracy `0.5334`, log loss `0.6993`, brier `0.4990`.
  - Asian handicap dynamic core: accuracy `0.5346`, log loss `0.6991`, brier `0.5001`.
  - All dynamic core: accuracy `0.5346`, log loss `0.6991`, brier `0.5001`.
- Total goals validation:
  - Rows `5330`; train `3476`; validation `891`; skipped `963`.
  - Close-market reference: accuracy `0.5174`, log loss `0.6927`, brier `0.4996`.
  - Static all-market model: accuracy `0.4994`, log loss `0.6991`, brier `0.5059`.
  - Total-goals dynamic core: accuracy `0.4938`, log loss `0.6991`, brier `0.5059`.
  - All dynamic core: accuracy `0.4938`, log loss `0.6993`, brier `0.5061`.
- Initial read: dynamic core features are not yet a clear win. Asian handicap has only a tiny accuracy lift with no log-loss improvement; total goals gets worse. Next modeling step should probably compare a less linear model or more targeted movement features before integrating this into recommendation logic.

HistGradientBoosting model comparison v1 completed:

- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Reports:
  - `docs/模型实验/20260529-baseline-asian-handicap-hgb-comparison-v1.md`.
  - `docs/模型实验/20260529-baseline-total-goals-hgb-comparison-v1.md`.
- Code behavior:
  - Static feature CSV still only runs the existing LogisticRegression variants.
  - Dynamic feature CSV now also runs `HistGradientBoostingClassifier` variants for the same feature groups.
- Asian handicap validation:
  - Close-market reference: accuracy `0.5287`, log loss `0.6971`, brier `0.4978`.
  - Best LogisticRegression accuracy: `0.5346` with dynamic core, log loss `0.6991`.
  - Best HGB accuracy: `0.5487` on `hgb_team_form_plus_all_markets`, log loss `0.7781`, brier `0.5166`.
  - HGB dynamic variants did not beat HGB static all-markets on accuracy.
- Total goals validation:
  - Close-market reference: accuracy `0.5174`, log loss `0.6927`, brier `0.4996`.
  - Best LogisticRegression accuracy: `0.4994` on static all-markets, log loss `0.6991`.
  - Best HGB accuracy: `0.5354` on `hgb_team_form_plus_all_markets`, log loss `0.7416`, brier `0.5399`.
  - HGB dynamic variants improved over LogisticRegression but did not beat HGB static all-markets on accuracy.
- Initial read: tree model learns useful direction signal, especially for total goals, but probabilities are poorly calibrated/too confident. Dynamic core features still are not clearly helpful. Next useful step is a probability calibration or edge-threshold backtest rather than adding this directly to recommendation logic.

Baseline edge-threshold backtest v1 completed:

- CLI command: `icewine samples baseline-edge-backtest`.
- Service: `src/icewine_prediction/baseline_edge_backtest_service.py`.
- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Report: `docs/模型实验/20260529-baseline-edge-backtest-v1.md`.
- Scope:
  - Asian handicap and total goals only.
  - Uses `HistGradientBoostingClassifier` with `team_form_plus_all_markets` features, because this was the best HGB accuracy variant in the previous comparison.
  - Compares raw HGB probabilities with sigmoid-calibrated HGB probabilities.
  - For each validation match, selects the side with the largest `model_probability - normalized_market_probability`, then evaluates thresholds `0.00`, `0.02`, `0.04`, `0.06`, `0.08`, `0.10`.
- Asian handicap:
  - Raw HGB all-threshold bets: `853`, accuracy `0.5522`, profit `60.3310`, ROI `0.0707`.
  - Raw HGB remains positive across thresholds through `0.10`, but log loss is poor (`0.7781`), so probability scale is not trustworthy.
  - Calibrated HGB all-threshold bets: `853`, accuracy `0.4853`, profit `-27.3720`, ROI `-0.0321`.
  - Calibrated HGB is positive only from threshold `0.02` upward, with very small samples at higher thresholds (`17` bets at `0.06`, `2` at `0.08`).
- Total goals:
  - Raw HGB all-threshold bets: `891`, accuracy `0.5320`, profit `23.3520`, ROI `0.0262`.
  - Raw HGB weakens as threshold rises and is nearly flat by `0.10`.
  - Calibrated HGB all-threshold bets: `891`, accuracy `0.4815`, profit `-39.0830`, ROI `-0.0439`.
  - Calibrated HGB is positive only at threshold `0.04`, with just `37` bets.
- Initial read: raw HGB shows positive ROI in this single validation split, especially Asian handicap, but calibration flips full-sample ROI negative. This suggests a real direction signal may exist, but probability calibration and edge threshold selection are not stable enough yet. Next useful step is walk-forward or repeated time-split validation before using any edge threshold in recommendation logic.

Baseline walk-forward edge backtest v1 completed:

- CLI command: `icewine samples baseline-walk-forward-edge`.
- Service: `src/icewine_prediction/baseline_walk_forward_edge_service.py`.
- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Report: `docs/模型实验/20260529-baseline-walk-forward-edge-v1.md`.
- Scope:
  - Asian handicap and total goals only.
  - Uses rolling chronological folds with train ratio `0.60`, validation ratio `0.10`, and `5` folds.
  - Per fold, compares raw HGB and sigmoid-calibrated HGB using `team_form_plus_all_markets` features.
  - Edge thresholds: `0.00`, `0.02`, `0.04`, `0.06`, `0.08`, `0.10`.
- Asian handicap:
  - Raw HGB threshold `0.00`: `2077` bets, positive ROI in `3/5` folds, average ROI `0.0402`, worst ROI `-0.0546`.
  - Raw HGB threshold `0.10`: `1266` bets, positive ROI in `4/5` folds, average ROI `0.0613`, worst ROI `-0.0050`.
  - Calibrated HGB threshold `0.00`: positive ROI in `1/5` folds, average ROI `-0.0260`.
  - Calibrated HGB high thresholds can show positive average ROI, but sample size collapses (`77` bets at `0.06`, `20` at `0.08`, `2` at `0.10`), so this is not reliable yet.
- Total goals:
  - Raw HGB threshold `0.00`: `2221` bets, positive ROI in `2/5` folds, average ROI `-0.0008`, worst ROI `-0.0424`.
  - Raw HGB remains roughly break-even to mildly negative across most thresholds.
  - Calibrated HGB threshold `0.00`: positive ROI in `0/5` folds, average ROI `-0.0607`.
- Initial read: this supports the concern that the single validation split was optimistic. Asian handicap raw HGB still has a possible signal, especially at stronger edge thresholds, but it is not stable enough for recommendation automation. Total goals has no clear edge yet. Next useful step is to build a recommendation sandbox/report that logs candidate picks without acting on them, or to improve probability calibration before any production recommendation threshold.

Baseline recommendation sandbox v1 completed:

- CLI command: `icewine samples baseline-recommendation-sandbox`.
- Service: `src/icewine_prediction/baseline_recommendation_sandbox_service.py`.
- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Report: `docs/模型实验/20260529-baseline-recommendation-sandbox-v1.md`.
- Scope:
  - Asian handicap only.
  - Uses raw HGB `team_form_plus_all_markets` on the existing train/validation split.
  - Filters candidate picks by `edge >= 0.10`.
  - This is an observation sandbox only. It writes a markdown report and does not create recommendation records or change source samples.
- Result:
  - Validation rows: `853`; candidates: `456`; displayed detail rows: `80`.
  - Total profit: `19.8310`; ROI `0.0435`.
  - Side split:
    - `away_cover`: `245` bets, `136` wins, profit `17.8500`, ROI `0.0729`.
    - `home_cover`: `211` bets, `110` wins, profit `1.9810`, ROI `0.0094`.
  - League distribution is broad, but league ROI is highly uneven. Examples:
    - Positive: Norway 1. Division `16` bets ROI `0.4133`; La Liga `16` bets ROI `0.3649`; Sweden Superettan `17` bets ROI `0.2552`; MLS `28` bets ROI `0.1186`.
    - Negative: Serie A `16` bets ROI `-0.4973`; J1 League `18` bets ROI `-0.3497`; Belgian Jupiler Pro League `12` bets ROI `-0.3582`.
- Initial read: the sandbox keeps the Asian handicap signal alive, especially on `away_cover`, but also shows clear direction and league sensitivity. Do not automate recommendations yet. Next useful step is to add walk-forward sandbox output or threshold comparison for candidate details, so we can see whether the `away_cover` bias and league effects persist across time folds.

Baseline walk-forward recommendation sandbox v1 completed:

- CLI command: `icewine samples baseline-walk-forward-sandbox`.
- Service: `src/icewine_prediction/baseline_walk_forward_sandbox_service.py`.
- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Report: `docs/模型实验/20260529-baseline-walk-forward-sandbox-v1.md`.
- Scope:
  - Asian handicap only.
  - Uses raw HGB `team_form_plus_all_markets`.
  - Rolling chronological folds with train ratio `0.60`, validation ratio `0.10`, `5` folds.
  - Filters candidate picks by `edge >= 0.10`, showing top `20` candidates per fold.
  - Observation sandbox only; does not create recommendation records or change source samples.
- Result:
  - Total candidates: `1266`; total profit `77.3850`; ROI `0.0611`.
  - Positive ROI folds: `4/5`.
  - Fold ROI:
    - Fold 1: `256` bets, ROI `0.0203`.
    - Fold 2: `242` bets, ROI `0.1177`.
    - Fold 3: `246` bets, ROI `-0.0050`.
    - Fold 4: `265` bets, ROI `0.0451`.
    - Fold 5: `257` bets, ROI `0.1284`.
  - Side stability:
    - `away_cover`: `610` bets, positive ROI in `5/5` folds, profit `52.3050`, ROI `0.0857`.
    - `home_cover`: `656` bets, positive ROI in `2/5` folds, profit `25.0800`, ROI `0.0382`.
- Initial read: this is the strongest evidence so far that the current Asian handicap signal is concentrated on the model-favored `away_cover` side. It is still not production-ready because probabilities remain poorly calibrated and league effects are uneven, but next work should prioritize an `away_cover`-focused threshold/league stability report before building any automated recommendation action.

Baseline away-cover stability v1 completed:

- CLI command: `icewine samples baseline-away-cover-stability`.
- Service: `src/icewine_prediction/baseline_away_cover_stability_service.py`.
- Input: `local_data/training/baseline_dynamic_features_main_leagues_20260529.csv`.
- Report: `docs/模型实验/20260529-baseline-away-cover-stability-v1.md`.
- Scope:
  - Asian handicap only.
  - Uses raw HGB `team_form_plus_all_markets`.
  - Only model-selected `away_cover` candidates are evaluated.
  - Rolling chronological folds with train ratio `0.60`, validation ratio `0.10`, `5` folds.
  - Thresholds: `0.08`, `0.10`, `0.12`, `0.15`, `0.20`.
- Threshold result:
  - `0.08`: `689` bets, positive ROI `4/5` folds, ROI `0.0606`, worst fold ROI `-0.0322`.
  - `0.10`: `610` bets, positive ROI `5/5` folds, ROI `0.0857`, worst fold ROI `0.0061`.
  - `0.12`: `535` bets, positive ROI `4/5` folds, ROI `0.0970`, worst fold ROI `-0.0143`.
  - `0.15`: `436` bets, positive ROI `3/5` folds, ROI `0.0820`, worst fold ROI `-0.1167`.
  - `0.20`: `293` bets, positive ROI `2/5` folds, ROI `0.0664`, worst fold ROI `-0.1051`.
- Line bucket result at primary threshold `0.10`:
  - `away_favorite`: `346` bets, ROI `0.0503`, positive ROI `2/5` folds.
  - `away_underdog`: `181` bets, ROI `0.1143`, positive ROI `4/5` folds.
  - `pickem`: `83` bets, ROI `0.1711`, positive ROI `3/5` folds.
- League result at threshold `0.10` is still noisy. Some leagues look strong, but many have low sample counts or a worst fold ROI of `-1.0000`, so do not hard whitelist/blacklist leagues yet.
- Initial read: `edge >= 0.10` is the best current away-cover threshold because it is the only tested threshold with positive ROI in all `5/5` folds and a positive worst fold. The more practical signal appears stronger in `away_underdog` and `pickem` than in `away_favorite`, but sample/fold stability is not yet enough for automation. Next useful step is a paper recommendation queue for future/upcoming matches using `away_cover`, `edge >= 0.10`, and a conservative tag that highlights line bucket and league risk.

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

## 2026-05-30 Latest Web Console Handoff

Latest committed work after this context update:

- Web console loading behavior was improved so the dashboard uses local API data by default and optional workspaces fall back section-by-section instead of replacing the full dashboard with mock data.
- Match list now uses explicit datetime filters:
  - default start: today 00:00 Beijing time
  - default end: tomorrow 12:00 Beijing time
  - frontend controls are `datetime-local`
  - backend API params are `start_time` and `end_time`
- Match list started/unscored matches are derived as `live`/`进行中`.
- Important bug fixed: derived status filtering now happens before applying the visible result limit, so `status_filter=live` is not accidentally emptied by the first 200 raw rows.
- Match-list league options now return `{ name, display_name }`; frontend displays Chinese `display_name` while submitting stable raw `name`.
- Local Web control script:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 start
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 stop
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 status
```

- `start_web.ps1` manages backend `127.0.0.1:8000` and frontend `127.0.0.1:5173`, writes runtime PID files under `.web/`, and `.web/` is gitignored.
- `scripts/start_web_api.ps1` intentionally runs uvicorn without `--reload` so stop/restart can manage the backend process reliably. Use `restart` after backend code changes.
- PowerShell may block direct `.\start_web.ps1 restart`; use the `-ExecutionPolicy Bypass -File` form above.

Fresh verification for this final Web handoff:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_match_list_workspace_service.py tests/test_web_console_api.py -q
```

Result: `30 passed`.

```powershell
cd web
npm test -- apiClient.test.ts matchListWorkspace.test.ts paperRecommendationWorkspace.test.ts
npm run build
```

Result: frontend tests `15 passed`; build succeeded.

`git diff --check` passed with only expected CRLF warnings.

Suggested next conversation setup:

1. Read `Agent.md`, `memory.md`, and this `Context.md`.
2. Start or restart Web with `powershell -ExecutionPolicy Bypass -File .\start_web.ps1 restart`.
3. Use `http://127.0.0.1:5173` for the local console.
4. Treat the latest Web match-list behavior as the baseline for future UI/data work.

## 2026-05-30 Web Paper Tracking And Match List Implementation

Implementation branch state:

- Committed design docs:
  - `5fc85b4 新增纸面推荐跟踪设计`
  - `311cb09 新增比赛列表同步页设计`
- Implementation is being committed after this context update. It includes backend services, API routes, React views, tests, and local startup behavior.

Paper recommendation tracking:

- Added `PaperRecommendationRecord` in `src/icewine_prediction/models.py`.
- Added `src/icewine_prediction/paper_recommendation_tracking_service.py`.
- Current strategy:
  - key: `asian_away_cover_hgb_edge_v1`
  - display name: `亚盘客队方向 · HGB边际 v1`
  - signal: Asian handicap `away_cover`, `edge >= 0.1000`
  - model: `raw_hgb_team_form_plus_all_markets`
- API routes in `src/icewine_prediction/web_api.py`:
  - `GET /api/paper-recommendations/workspace`
  - `POST /api/paper-recommendations/records`
  - `POST /api/paper-recommendations/records/backfill`
  - `PATCH /api/paper-recommendations/records/{record_id}`
  - `POST /api/paper-recommendations/settle`
  - `POST /api/paper-recommendations/records/{record_id}/void`
- Web page: sidebar item `纸面跟踪`, with candidate queue, records, manual edit, void, settlement, and grouped summaries.
- Important display rule remains: show Beijing time, Chinese league/team names, and explicit handicap such as `客队 +0.50`.

Historical paper backfill done in local DB:

- Root cause: the 2026-05-30 early-morning candidate existed only in `docs/模型实验/20260530-paper-recommendation-queue-v1.md`; no `paper_recommendation_records` row had been created before kickoff.
- Backfilled local record:
  - record id: `1`
  - match id: `17446`
  - source match id: `1492706`
  - fixture: `爱超 德罗赫达联 vs 沃特福德联`
  - kickoff: `2026-05-30 02:45` Beijing time
  - recommendation: `客队 +0.50`
  - odds: `1.930`
  - model p: `0.6044`
  - market p: `0.4880`
  - edge: `0.1164`
  - status: `pending`
  - manual note: `从 20260530 paper queue 报告补录；原候选生成于 2026-05-30 01:21 北京时间。`
- Duplicate active backfill is rejected with `duplicate active paper recommendation record`.

Match list and sync page:

- Added `DataSyncRun` in `src/icewine_prediction/models.py`.
- Added `src/icewine_prediction/match_list_workspace_service.py`.
- API routes:
  - `GET /api/match-list/workspace`
  - `POST /api/match-list/sync/fixtures-results`
  - `POST /api/match-list/sync/odds`
  - `GET /api/matches/{match_id}/detail`
- Web page: sidebar item `比赛列表`.
- Default list window: `next_24h`.
- Top strip: compact freshness and sync controls.
- Filters: time preset, league, status, odds availability, search.
- Detail view: opens from a match row; shows logos, teams, score/status, odds summary, team-data placeholder, and recommendation-summary placeholder for future linking.

Web local data behavior:

- `web/src/apiClient.ts` now keeps `source: "api"` when core local APIs succeed.
- Optional sections such as paper recommendations, match list, training workspace, audit, and odds trend fall back section-by-section instead of turning the entire dashboard into mock data.
- `scripts/start_web_frontend.ps1` clears `VITE_API_BASE_URL` so the frontend uses Vite same-origin `/api` proxy to `http://127.0.0.1:8000`.
- Current dev servers were restarted:
  - backend: `http://127.0.0.1:8000`
  - frontend: `http://127.0.0.1:5173`

Fresh verification before commit:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_tracking_service.py tests/test_match_list_workspace_service.py tests/test_web_console_api.py -q
```

Result: `29 passed`.

```powershell
cd web
npm test -- apiClient.test.ts matchListWorkspace.test.ts paperRecommendationWorkspace.test.ts
npm run build
```

Result: frontend tests `9 passed`; build succeeded.

Suggested next conversation directions:

1. Paper recommendation settlement loop:
   - Sync finished results for paper-record matches.
   - Settle pending records after scores are available.
   - Decide whether settlement button should stay hidden/manual or be exposed later.
   - Add paper-record summary/jump from match detail once the UX is ready.
2. Match list Web验收/迭代:
   - Use the `比赛列表` page against real local data.
   - Confirm sync buttons, default next-24h list, filtering, and detail page behavior.
   - Improve detail content when team stats/standings/recommendation links become available.

## 2026-05-30 Web Sync Diagnostics, Cleanup, And Odds-Failure Handoff

Latest work pending commit after this handoff:

- Added persistent per-match sync details:
  - Model/table: `DataSyncRunItem`.
  - API: `GET /api/data-sync-runs/{run_id}/items`.
  - Web: `最近同步诊断` panel with collapsible success/failed/skipped details.
  - Useful for next odds-failure diagnosis: inspect the latest odds sync run items first, then join to `odds_source_matches` and `historical_odds_snapshots`.
- Fixed confusing diagnostics display:
  - OddsPapi diagnostic fields (`diagnostic_status`, `source_fixture_id`, `snapshot_count`, `diagnostic_error`) are shown only for odds sync.
  - Fixtures/results sync no longer displays stale odds diagnostics such as `诊断: success · 快照 151`.
- API-Football stability:
  - `ApiFootballClient` now supports request cooldown, one retry, retry cooldown, and wraps `requests.RequestException` as `ApiFootballApiError`.
  - `build_api_football_provider` passes defaults: `request_cooldown_seconds=0.8`, `max_retries=1`, `retry_cooldown_seconds=2.0`.
  - `同步赛程/赛果` lazily initializes the provider so fully skipped batches use `0` requests.
  - Truly live/in-play matches are skipped for result sync with message `比赛进行中，暂不申请赛果`.
  - Live detection checks `status`, `status_short`, and `status_long` lowercased against:
    `live`, `in_play`, `halftime`, `1h`, `2h`, `ht`, `et`, `bt`, `p`, `int`, `susp`.
- Raw historical odds duplicate fix:
  - Historical odds raw/snapshot unique-key comparison normalizes `market_line` to `0.01` and timezone-aware `snapshot_time` to naive UTC before de-duping.
  - This fixed the SQLite unique-key failure seen in earlier odds sync runs.
- OddsPapi fixture lookup diagnostics:
  - Non-404 fixture lookup `OddsPapiApiError` now stores/updates `OddsSourceMatch` as `historical_odds_status="fixture_lookup_failed"` with the error text.
  - 404/unavailable behavior remains separate.
- Match-list status display:
  - Started/no-score matches display `pending_result` / `待填赛果`.
  - `scheduled`/`not_started` display `未开赛`.
- Web console cleanup:
  - Default page is now `比赛列表`.
  - Sidebar intentionally shows only:
    `比赛列表`, `中文名`, `模型训练`, `纸面跟踪`, `推荐记录`.
  - Overview, coverage, worker, Oddspapi audit, unmatched, and standalone odds-trend pages are hidden from navigation but not deleted.
  - `mockDashboardData.recommendationRecords` is empty.
  - Local SQLite table `recommendation_records` was cleared on 2026-05-30:
    deleted `11`, remaining `0`.
  - `paper_recommendation_records` was not cleared and had `6` rows at cleanup time.
  - Web was restarted after clearing `recommendation_records`; `/api/recommendation-records` returned `Count: 0`.

Fresh verification run before this handoff:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py tests/test_match_list_workspace_service.py tests/test_api_football_client.py -q
```

Result: `45 passed`.

```powershell
cd web
npm test
npm run build
```

Result: frontend `44 passed`; build succeeded.

Useful next odds-failure diagnosis flow:

1. Run or inspect latest odds sync from Web.
2. Query latest run:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
@'
from icewine_prediction.database import create_database_engine, create_session_factory, initialize_database
from icewine_prediction.models import DataSyncRun, DataSyncRunItem
engine=create_database_engine(); initialize_database(engine); Session=create_session_factory(engine)
with Session() as s:
    run=s.query(DataSyncRun).filter_by(sync_type="odds").order_by(DataSyncRun.id.desc()).first()
    print(run.id, run.status, run.created_count, run.skipped_count, run.requests_used, run.error_message)
    for item in s.query(DataSyncRunItem).filter_by(run_id=run.id).order_by(DataSyncRunItem.status, DataSyncRunItem.match_id):
        print(item.status, item.match_id, item.message, item.diagnostic_status, item.source_fixture_id, item.snapshot_count, item.diagnostic_error)
'@ | C:\ProgramData\anaconda3\python.exe -
```

3. For failures, classify using `diagnostic_status`:
   - `fixture_lookup_failed`: API/transport/provider failure during OddsPapi fixture lookup; error text should now be persisted.
   - `unmatched`: no OddsPapi fixture matched by teams/time/league mapping.
   - `unavailable`: usually 404/unavailable fixture.
   - `empty`: fixture matched but no usable pre-match/main-line odds.
   - missing source row after this commit should be treated as a bug worth investigating.

4. Do not call Oddspapi for local audits unless explicitly probing/fetching. The web sync and `oddspapi_sync_runner` calls do consume API requests.

## 2026-05-31 Match List Sync, Paper Queue, And OddsPapi 429 Fixes

Work completed and prepared for commit on 2026-05-31:

- Result sync:
  - `_is_live_match_for_result_sync` now only skips in-play/live statuses while they are within 2 hours after kickoff.
  - Stale live statuses older than that are refreshed via API-Football so finished scores can be backfilled.
  - API-Football fixture mapping uses `score.fulltime` for the main stored score when present, falling back to `goals`; extra time and penalty scores remain in their separate fields.
- Paper recommendation queue:
  - `asian_away_cover_hgb_edge_v1` candidates now require a usable Asian handicap odds snapshot within 3 hours before kickoff.
  - Rows without sufficiently fresh odds are marked `stale_odds`.
  - Paper tracking workspace receives only rows with `status == "candidate"`.
  - Cleared obsolete local `paper_recommendation_records` rows earlier in this session; one pending record remained at that time.
- Match list UI:
  - Removed the `核心盘口` column from the match list table and row model.
  - Backend odds summary remains available for details/diagnostics.
- OddsPapi fixture lookup:
  - Fixed Superettan-style filtered fixture misses by retrying unfiltered fixture lookup when filtered candidates exist but do not match teams.
  - Diagnosed web odds sync 429s as fixture endpoint short-window limiting, not total quota exhaustion.
  - `OddsPapiSyncClient` fixture cooldown default is now 7.5 seconds.
  - The 404 filtered-fixture fallback now records the first request and waits before sending the unfiltered request.
  - `run_oddspapi_sync` and `run_oddspapi_sync_result` use `GLOBAL_FIXTURE_LIMITER`, so repeated Web/manual single-match clicks share the 7.5s fixture limiter.

Fresh verification for the final state:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_oddspapi_sync_runner.py -q
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q
```

Result during implementation: `52 passed` and `32 passed`.

Frontend checks run after removing the match-list core-handicap column:

```powershell
cd web
npm test -- matchListWorkspace.test.ts
npm run build
```

Result during implementation: match-list test passed and build succeeded.

## 2026-05-31 Liga MX Addition And OddsPapi Backfill

Work completed in this session:

- Added Liga MX / 墨西超 as an enabled main league:
  - `config/leagues.yaml`: `Liga MX`, country `Mexico`, API-Football id `262`, priority `50`.
  - `config/display_names.yaml`: `Liga MX` and `Liga MX (Mexico)` display as `墨西超`.
  - The user filled the 18 Liga MX team Chinese display names in `config/display_names.yaml`.
- Added OddsPapi tournament mapping:
  - `262 -> 27466` (`Liga MX, Clausura`) in `src/icewine_prediction/oddspapi_sync_runner.py`.
  - Important nuance: Oddspapi also has `27464` for `Liga MX, Apertura`. For the stable window after `2026-01-15`, API-Football fixtures are Clausura, so `27466` is correct. If backfilling 2025 H2 / Apertura later, mapping support may need to become season/round aware instead of one API-Football league id to one tournament id.
- Synced API-Football schedule/results:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli sync history --league-id 262 --season 2025
```

Result: `history:262:2025: created=337, updated=0, skipped=0, requests=1`.

Local DB after sync:

- League row: `Liga MX (Mexico)`, source league id `262`, enabled.
- Season `2025` total matches: `337`.
- Finished/scored matches on or after `2026-01-15`: `154`.
- Teams: Atlas, Atletico San Luis, CF Pachuca, Club America, Club Queretaro, Club Tijuana, Cruz Azul, FC Juarez, Guadalajara Chivas, Leon, Mazatlán, Monterrey, Necaxa, Puebla, Santos Laguna, Tigres UANL, Toluca, U.N.A.M. - Pumas.

OddsPapi worker command used:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m icewine_cli odds-source oddspapi-worker-start `
  --season 2025 `
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
  --league-ids 262 `
  --from-date 2026-01-15 `
  --notify-on-complete
```

Worker final status:

- Process: `pid=19052`, stopped/done.
- Logs:
  - `logs\odds\20260531-100540-oddspapi-worker-process.log`
  - `logs\odds\20260531-100541-pid19052-oddspapi-batch-worker.log`
- Summary: processed `154/154`, snapshots `20424`, requests `297`, worker summary `failed=1`.
- DB final status after worker:
  - success `140`
  - empty `14`
  - unmatched `0`
  - unavailable `0`
  - fixture_lookup_failed `0`
  - failed `0`
- Three-market snapshot coverage:
  - asian_handicap: `140` matches, `6752` snapshots.
  - total_goals: `140` matches, `6742` snapshots.
  - match_winner: `140` matches, `6930` snapshots.
  - Complete three-market coverage: `140/154` (`90.9%`).
- The worker-level `failed=1` was a historical-odds timeout for match `18651` Club America vs Tigres UANL. It was retried later by the same worker and did not remain failed in DB.
- The `14` empty matches matched OddsPapi fixtures but produced no usable pre-match/main-line snapshots. These are not alias problems.

Focused verification run before commit:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_settings.py tests/test_display_service.py tests/test_oddspapi_sync_runner.py::test_api_football_league_mappings_include_new_main_leagues -q
```

Result: `9 passed`.

## 2026-05-31 Web Model Training Mock Panel Cleanup

Work completed in this session:

- Cleaned the Web model-training page by removing three mock-only bottom panels:
  - `最近训练结果`
  - `模型盘口覆盖`
  - `联赛训练覆盖`
- Removed the unused frontend mock/type/helper chain that only supported those panels:
  - `ModelTrainingOverview`, `ModelTrainingRun`, `ModelLeagueTrainingCoverage`, and `ModelTrainingStatus`.
  - `mockModelTrainingOverview`.
  - `buildModelTrainingSummaryCards`, `listRecentModelRuns`, and `formatModelTrainingStatus`.
- `DashboardData` and `loadDashboardData()` no longer carry the mock model-training overview. The page keeps the real training workspace/orchestration, data quality, and close-market baseline sections.
- Existing local user changes in `.gitignore` and `docs/数据审计/20260529-baseline-training-dataset.md` were intentionally left untouched.

Frontend verification run:

```powershell
cd web
npm test -- modelTrainingWorkspace.test.ts
npm test
npm run build
```

Result: focused helper test `5 passed`; full frontend tests `41 passed`; production build succeeded.

## 2026-06-06 Execution Timepoint Alignment And Manual Odds Supplement

Recent commits relevant to the current handoff:

- `8fa1860 Unify execution timepoint snapshot selection`
- `583ebc1 完善赔率标准时点补齐与详情页覆盖展示`
- `1cdea63 修正定向赔率回填计数口径`
- `9121aa2 支持手动补录标准时点赔率`
- `e1b7d6d 手动修改别名`

Core product decision:

- The user wants scheduled paper candidates, finished-match historical paper replay, and training/signal discovery to use aligned odds timepoint口径.
- Current standard execution targets are `T-60/T-30/T-25/T-20/T-15/T-10`.
- T-n selection uses shared `±5` minute tolerance via `execution_timepoint_service.DEFAULT_EXECUTION_TIMEPOINT_TOLERANCE_MINUTES`.
- Candidate decision price is T-10 oriented and can fall back through earlier available targets up to T-30. Robustness observations use the broader target set, including T-60.
- `latest/T-5` style near-final close prices should not be reintroduced into this aligned paper-candidate flow without an explicit design change.

Implemented odds snapshot tooling:

- Raw supplement command/script:
  - Script: `scripts/supplement_historical_odds_snapshots_from_raw.sh`
  - CLI command: `icewine_cli odds-source oddspapi-supplement-snapshots-from-raw`
  - It supplements missing standard target groups from `historical_odds_raw_snapshots` into `historical_odds_snapshots` where raw data has an eligible current main-market snapshot.
- Historical snapshot sampling density was increased enough to preserve standard target points.
- Match detail page displays a standard timepoint coverage matrix:
  - Markets: Asian handicap / total goals / match winner.
  - Targets: `T-60/T-30/T-25/T-20/T-15/T-10`.
  - Health label/colors are based on available cells.
- Manual supplement endpoint:
  - `POST /api/matches/{match_id}/execution-timepoint-odds/manual`
  - Payload fields: `target_minutes_before_kickoff`, `market_type`, `market_line`, `odds_by_side`, optional `note`.
  - Writes rows into `historical_odds_snapshots` as `source_name=oddspapi`, `bookmaker=pinnacle`.
  - Marks manual origin with `market_id=manual-...`, manual `market_name`, and `raw_payload.source=manual`.
  - Does not overwrite an already-covered standard cell; duplicate/covered requests return `already_exists`.
- Frontend behavior:
  - Existing coverage cells do not render edit buttons.
  - Missing cells render a compact plus button and form.
  - Form side fields are market-aware: Asian handicap `home/away`, total goals `over/under`, match winner `home/draw/away`.
  - Successful supplement reloads the match detail so coverage refreshes immediately.

Verified manual supplement example:

- Match: `16686`, Daegu FC vs Paju Citizen, kickoff `2026-06-05 18:30` Beijing time.
- User manually added:
  - Asian handicap `T-60`, line `-1.25`, home `2.06`, away `1.81`.
  - Match winner `T-10`, home `1.42`, draw `4.48`, away `6.72`.
- DB verification:
  - Rows exist in `historical_odds_snapshots`.
  - `source_name=oddspapi`, `bookmaker=pinnacle`.
  - Market ids are `manual-asian_handicap-T60` and `manual-match_winner-T10`.
  - `raw_payload` includes `"source": "manual"`.
- Service verification:
  - `build_match_detail(session, match_id=16686)` reports coverage `16/18`, health `medium/可用`.
  - Manual Asian handicap T-60 and match-winner T-10 are selected by the standard coverage logic.
  - `build_paper_recommendation_queue` for the 2026-06-05 Beijing-day window returns 3 candidate rows for this match:
    - `asian_away_cover_hgb_edge_v1`
    - `total_goals_hgb_bucket_v2`
    - `asian_away_cover_hgb_bucket_v2`
  - The Asian handicap robustness observed targets include `(10, 15, 20, 25, 30, 60)`, proving the manual T-60 row is consumed by the paper-candidate path.

Signal/strategy state from this round:

- Removed `total_goals_hgb_confirmed_under_mid_275_v1`; it was sample-poor after rerun and not worth keeping.
- Kept `total_goals_hgb_low_line_bucket_v3`, but its own signal contribution is capped/lower. It should not cap the whole same-direction confidence group if other stronger signals trigger.
- Added/kept newer formal paper signals to increase paper observation volume. Chinese display names should be used in Web, including the paper tracking `按策略` tab.
- Existing paper records were cleared multiple times during this work so the user could replay from 2026-05-29 onward under the new口径.

Fresh verification before commit `9121aa2`:

```powershell
$env:PYTHONPATH='src'; C:/ProgramData/anaconda3/python.exe -m pytest tests/test_historical_odds_service.py tests/test_web_console_api.py -q
cd web; npm test
cd web; npm run build
git diff --check
```

Results:

- Backend focused tests: `70 passed`.
- Frontend tests: `59 passed`.
- Frontend build succeeded.
- `git diff --check` passed with only CRLF warnings.

Later full backend verification during the same feature work:

```powershell
$env:PYTHONPATH='src'; C:/ProgramData/anaconda3/python.exe -m pytest -q
```

Result: `593 passed, 20 warnings` (sklearn imputer warnings already known).

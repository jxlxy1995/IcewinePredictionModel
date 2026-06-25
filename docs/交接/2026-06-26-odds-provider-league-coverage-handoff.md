# Odds Provider League Coverage Handoff

Date: 2026-06-26

## Background

This handoff records the league coverage work after moving the primary odds source from OddsPapi/Pinnacle to The Odds API/Pinnacle, with Oddspapi/SBOBet as a trusted fallback for selected leagues.

The current read priority for trusted historical snapshots is:

1. `the_odds_api / pinnacle`
2. `oddspapi / pinnacle`
3. `oddspapi / sbobet`

SBOBet is treated as functionally trusted for model and candidate calculations when Pinnacle is unavailable. It remains source-labeled for display/debugging.

## The Odds API Coverage

The Odds API `sports?all=true` was checked on 2026-06-26. The code mapping now covers 40 enabled whitelist leagues via `API_FOOTBALL_TO_THE_ODDS_API_SPORT_KEYS` in `src/icewine_prediction/the_odds_api_sync_runner.py`.

New mappings added in this pass:

| API-Football ID | League | The Odds API sport key |
| --- | --- | --- |
| `2` | UEFA Champions League | `soccer_uefa_champs_league` |
| `3` | UEFA Europa League | `soccer_uefa_europa_league` |
| `848` | UEFA Europa Conference League | `soccer_uefa_europa_conference_league` |
| `141` | Segunda Division | `soccer_spain_segunda_division` |
| `144` | Jupiler Pro League | `soccer_belgium_first_div` |
| `203` | Super Lig | `soccer_turkey_super_league` |
| `197` | Super League 1 | `soccer_greece_super_league` |
| `218` | Bundesliga Austria | `soccer_austria_bundesliga` |
| `207` | Super League Switzerland | `soccer_switzerland_superleague` |
| `235` | Premier League Russia | `soccer_russia_premier_league` |
| `106` | Ekstraklasa | `soccer_poland_ekstraklasa` |
| `119` | Superliga Denmark | `soccer_denmark_superliga` |
| `128` | Liga Profesional Argentina | `soccer_argentina_primera_division` |
| `265` | Primera Division Chile | `soccer_chile_campeonato` |
| `244` | Veikkausliiga | `soccer_finland_veikkausliiga` |
| `113` | Allsvenskan | `soccer_sweden_allsvenskan` |
| `114` | Superettan | `soccer_sweden_superettan` |
| `41` | League One England | `soccer_england_league1` |
| `103` | Eliteserien | `soccer_norway_eliteserien` |
| `307` | Saudi Pro League | `soccer_saudi_arabia_pro_league` |
| `169` | Super League China | `soccer_china_superleague` |

Smoke checks after adding mappings:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli odds-source the-odds-api-plan --season 2026 --max-matches 1 --league-ids 169 --from-date 2026-06-26
```

Result: China Super League entered The Odds API plan with `soccer_china_superleague`.

```powershell
C:\ProgramData\anaconda3\python.exe -m icewine_prediction.cli odds-source the-odds-api-plan --season 2026 --max-matches 1 --league-ids 120 --from-date 2026-06-26
```

Result: Denmark 1st Division did not enter The Odds API plan, as expected.

## The Odds API Unsupported or Unmapped Whitelist Leagues

The Odds API did not expose matching soccer sport keys for these enabled whitelist leagues:

| API-Football ID | League | Current decision |
| --- | --- | --- |
| `89` | Eerste Divisie | no The Odds API key found |
| `283` | Liga I Romania | no The Odds API key found |
| `104` | Norway 1. Division | SBOBet fallback verified |
| `1087` | Finland Ykkosliiga | SBOBet fallback verified |
| `120` | Denmark 1. Division | SBOBet fallback verified |
| `358` | Ireland First Division | SBOBet fallback verified |
| `164` | Iceland Urvalsdeild | SBOBet fallback verified |
| `274` | Indonesia Liga 1 | SBOBet fallback verified, team alias recommended |
| `293` | K League 2 | fixture/markets verified, historical odds 404 |

J2 League (`99`) is disabled in `config/leagues.yaml`, has no local League/Match sample in the database used for this check, and has no Oddspapi tournament mapping yet.

## SBOBet Fallback Verification

Verified fallback league IDs are recorded in `SBOBET_FALLBACK_API_FOOTBALL_LEAGUE_IDS` in `src/icewine_prediction/oddspapi_sync_runner.py`:

```python
frozenset({"104", "120", "164", "274", "358", "1087"})
```

These leagues passed fixture matching, market definition lookup, and `historical-odds` payload retrieval for SBOBet:

| API-Football ID | League | Oddspapi tournament | Probe status |
| --- | --- | --- | --- |
| `120` | Denmark 1. Division | `47` | historical odds OK |
| `1087` | Finland Ykkosliiga | `55` | historical odds OK |
| `104` | Norway 1. Division | `22` | historical odds OK |
| `358` | Ireland First Division | `193` | historical odds OK |
| `164` | Iceland Urvalsdeild | `188` | historical odds OK |
| `274` | Indonesia Liga 1 | `1015` | historical odds OK, alias needed |

Indonesia note:

The sample match was `Pusamania Borneo vs Malut United`; Oddspapi fixture team was `Borneo Samarinda vs Malut United`. Match confidence was only `0.5`, so add a team alias before relying on large-scale automated matching:

```yaml
- entity_type: team
  source_name: oddspapi
  canonical_name: Pusamania Borneo
  alias_name: Borneo Samarinda
```

## K2 Status

K League 2 (`293`) should not be enabled as stable SBOBet fallback yet.

Observed on 2026-06-26:

- Oddspapi tournament mapping exists: `293 -> 777`
- Fixture matching works
- SBOBet market definitions work
- SBOBet `historical-odds` returned `404` for 5 future samples

Samples checked:

| Match | Fixture | Result |
| --- | --- | --- |
| Ansan Greeners vs Suwon City FC | `id1000077768046576` | historical-odds 404 |
| Suwon Bluewings vs Seongnam FC | `id1000077768046580` | historical-odds 404 |
| Chungbuk Cheongju FC vs Daegu FC | `id1000077768046574` | historical-odds 404 |
| Paju Frontier FC vs Yongin City FC | `id1000077768046578` | historical-odds 404 |
| Gyeongnam FC vs Cheonan City FC | `id1000077768046586` | historical-odds 404 |

Next action when K2 has closer or active fixtures:

1. Re-run fixture matching for `league_ids=293`.
2. Probe `historical-odds` on SBOBet after the fixtures are closer to kickoff or finished.
3. Add `293` to `SBOBET_FALLBACK_API_FOOTBALL_LEAGUE_IDS` only after at least one historical-odds payload succeeds.

## J2 Status

J2 League (`99`) is pending.

Current facts:

- `config/leagues.yaml` has J2, but `enabled: false`
- No local League/Match sample was found in the database used for the probe
- `API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS` has no `99` mapping
- The Odds API only exposes `soccer_japan_j_league`, which maps to J1, not J2

Next action when J2 is needed:

1. Enable or import J2 schedule samples.
2. Identify the Oddspapi tournament id for J2.
3. Probe SBOBet fixture matching and markets.
4. Probe SBOBet `historical-odds`.
5. Add J2 to fallback only after historical-odds succeeds.

## Manual Pinnacle Replacement Note

Match detail can clear the currently selected SBOBet group before manual Pinnacle entry.

The clear action deletes only `historical_odds_snapshots` rows for the match where
`source_name = oddspapi` and `bookmaker = sbobet`. It intentionally does not delete
`historical_odds_raw_snapshots`, Pinnacle rows, or The Odds API rows.

Because of this, it is expected that raw snapshots may still contain SBOBet data while
the standardized main table has Pinnacle rows or no selected rows for the same match.
Treat raw as source evidence and `historical_odds_snapshots` as the current model/display
main table.

## Verification

Tests added/updated:

- `tests/test_the_odds_api_sync_runner.py::test_sport_key_mapping_covers_the_odds_api_supported_whitelist_leagues`
- `tests/test_oddspapi_sync_runner.py::test_sbobet_fallback_leagues_include_only_verified_historical_odds_targets`

Verification command:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_the_odds_api_sync_runner.py tests/test_oddspapi_sync_runner.py tests/test_oddspapi_batch_backfill_service.py tests/test_match_odds_sync_service.py -q
```

Result:

```text
101 passed in 38.58s
```

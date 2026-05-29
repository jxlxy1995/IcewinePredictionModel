# Project Memory

## Stable Decisions

- OddsPapi historical data is considered reliable mainly from `2026-01-15` onward.
- Coverage reports for odds planning should generally use finished matches after `2026-01-15` as denominator.
- Main odds snapshots should store only the selected main line for each market.
- Raw odds summary can keep compact neighboring lines around the main line for later analysis.
- Three markets matter for model training:
  - Asian handicap
  - Total goals
  - Match winner
- Earlier old-format odds data lacked match-winner odds and may have selected non-main lines. Most old-format leagues have now been rerun.
- UTC storage/parsing is fine; user-facing display should use Beijing time.

## Oddspapi Backfill Learnings

- Safe single-worker mode is the default for long runs to reduce 429 risk.
- `chunk-size=4`, cooldown `7.5s`, and round timeout `500s` have been working well.
- Historical odds requests usually take around 5-8 seconds when healthy.
- Some early boundary matches return raw data but no usable pre-match/main-line snapshots; these are usually marked `empty`.
- Rechecked non-matching fixtures should be marked `unavailable`, not left as `unmatched`, when candidates clearly do not match target teams.
- Current `unmatched_count` was cleared to `0` on 2026-05-29.

## Important Mappings Added

Tournament mappings recently added:

- `98 -> 196` J1 League
- `253 -> 242` MLS
- `292 -> 410` K League 1
- `293 -> 777` K League 2
- `197 -> 185` Greek Super League
- `307 -> 955` Saudi Pro League

Alias mappings recently added include:

- Ulsan Hyundai FC -> Ulsan HD FC
- Jeju United FC -> Jeju SK FC
- Asan Mugunghwa -> Chungnam Asan FC
- AEK Athens FC -> AEK Athens
- Olympiakos Piraeus -> Olympiacos Piraeus
- Al-Ittihad FC -> Al-Ittihad Club
- Al-Qadisiyah FC -> Al Qadsiah
- Al-Hilal Saudi FC -> Al Hilal SFC
- Volos NFC -> Volos NPS
- Al Taawon -> Al-Taawoun FC
- Al-Ettifaq -> Al-Ittifaq FC
- Panetolikos -> Panaitolikos Agrinio
- Larisa -> AE Larissa FC

## Code Fixes Already Committed

Commit `89efda1 Improve Oddspapi backfill tooling and aliases` includes:

- `match_ids` support for targeted Oddspapi worker/backfill/fetch flows.
- `oddspapi-sample-candidates` command.
- Worker process propagation of `match_ids`.
- Weak overlap token handling for `"al"` to avoid false team matches.
- Tests for these behaviors.

Focused verification at that time: `90 passed`.

## League Naming Notes

- `Superettan` should be called 瑞典超甲, not 瑞典甲.
- 德丙 has been removed from the desired whitelist direction because odds coverage was 0 in the current stable window.


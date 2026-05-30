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
- Web console should default to local real API data. Mock data is only a fallback when local API data is unavailable, preferably scoped to the failed section rather than replacing the whole dashboard.
- Web match list defaults to local real data for today 00:00 through tomorrow 12:00 Beijing time, using explicit datetime controls rather than future-N-day presets.
- Web match-list league filters should display Chinese league names while preserving raw league names as stable filter values.
- Started matches with no recorded score should be displayed and filterable as live/in-progress. Apply derived status filtering before list limiting so live matches are not hidden by the display cap.
- Use `start_web.ps1` as the unified Web control script for start/stop/restart/status. Backend runs without `uvicorn --reload`; restart the script after backend code changes.
- Paper/formal recommendation strategies should have a memorable Chinese display name, with English keys/model names allowed as secondary technical identifiers.
- Paper recommendation records are independent tracking records. Missed queue candidates can be backfilled from historical paper queue reports, but should be marked as manual/backfill rather than pretending they were automatic clicks.
- Web console navigation is intentionally focused on active workflows: match list, Chinese names, model training, paper tracking, and recommendation records.
- Formal `recommendation_records` local demo data was cleared on 2026-05-30; keep `paper_recommendation_records` separate and do not clear it when only cleaning the recommendation-record page.
- Result sync should not request API-Football fixture updates for truly live/in-play matches; skip them and retry after they are no longer live.
- Result sync should only skip live/in-play matches during the first 2 hours after kickoff; stale live statuses after that should be refreshed so final results can be backfilled.
- API-Football main score should use `score.fulltime` when present, falling back to `goals`; this keeps stored match scores as regular-time scores and excludes extra time / penalties from the main result fields.
- API-Football requests should be gently paced and retried once for transient connection resets.
- Match sync diagnostics should be persisted per match. Odds diagnostics belong only to odds sync reports, not fixtures/results sync reports.
- Paper recommendation candidates for `asian_away_cover_hgb_edge_v1` should require a usable Asian handicap odds snapshot within 3 hours before kickoff; stale/no-odds rows stay visible in queue diagnostics but must not enter the recordable paper workspace.

## Oddspapi Backfill Learnings

- Safe single-worker mode is the default for long runs to reduce 429 risk.
- `chunk-size=4`, cooldown `7.5s`, and round timeout `500s` have been working well.
- Web/manual OddsPapi fixture lookups also use a 7.5s shared limiter. The 404 filtered-fixture fallback must wait before sending the unfiltered fixture request, and consecutive Web clicks should share the same limiter.
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

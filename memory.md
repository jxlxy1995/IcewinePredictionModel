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
- The Web model-training page should only show real training workspace/orchestration artifacts. Do not reintroduce mock-only panels for recent model runs, model market coverage, or league training coverage unless a real backend source is added first.
- Training, finished-match paper replay, and scheduled-match paper candidates should stay aligned around standard execution-timepoint odds rather than mixing latest/near-close definitions.
- Standard execution timepoints are currently `T-60/T-30/T-25/T-20/T-15/T-10` with shared `±5` minute tolerance. T-10 is the primary decision target; missing T-10 can search backward through T-30 before rejecting.
- Raw-to-standard historical odds supplement should fill missing standard target groups from `historical_odds_raw_snapshots` when possible, but only with the current main-market definition.
- Manual standard-timepoint odds supplement is intentionally written into `historical_odds_snapshots` as `oddspapi/pinnacle` so existing training/replay/paper-candidate paths consume it without a special read path. Manual rows are marked by `manual-` market ids and `raw_payload.source=manual`.
- Manual standard-timepoint supplement must not overwrite already-covered cells. Backend returns `already_exists`; frontend should not render edit buttons for existing coverage cells.
- `total_goals_hgb_confirmed_under_mid_275_v1` was removed after rerun/inspection because it remained sample-poor and not worth keeping. `total_goals_hgb_low_line_bucket_v3` remains but its own signal contribution is capped/lower; it should not cap the whole same-direction group if stronger signals also trigger.
- Paper signal pool currently includes the older selected strategies plus newer formalized observation strategies from the T-10-aligned run: Asian away cover HGB edge/bucket, Asian home favorite bucket, total goals HGB bucket/low-line/low-under, and total-goals distribution confirmed variants. Keep Chinese strategy names in Web displays, including the "按策略" tab.
- Paper tracking top-level summary and confidence-simulation/group summary have different statistical口径 by design; rename labels for clarity rather than forcing them into one metric.

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
- `262 -> 27466` Liga MX, Clausura

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

## Liga MX Addition

- Liga MX / 墨西超 was added as an enabled main league with API-Football id `262`, season `2025`.
- API-Football `history:262:2025` created `337` local matches. The current cross-year season runs from 2025-07 to 2026-05, so `season=2025` is the right sync/backfill season.
- Finished/scored matches on or after `2026-01-15`: `154`.
- OddsPapi tournament mapping uses `262 -> 27466` (`Liga MX, Clausura`) for the stable post-2026-01-15 window. `27464` is the Apertura tournament and should only be considered if backfilling 2025 H2 before the stable boundary.
- OddsPapi safe worker completed for Liga MX on 2026-05-31:
  - processed `154/154`, snapshots `20424`, requests `297`, worker summary `failed=1`.
  - DB final status: success `140`, empty `14`, unmatched/unavailable/fixture_lookup_failed/failed `0`.
  - The one worker-level failure was a historical-odds timeout for match `18651` Club America vs Tigres UANL; it was retried later in the same worker and did not remain failed in DB.
  - Complete three-market coverage after the run: `140/154` (`90.9%`).
  - The `14` empty matches matched fixtures but had no usable pre-match/main-line snapshots, mostly around the 2026-01-15 boundary plus a few February/playoff matches.

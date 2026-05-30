# Match List Filtered Sync Design

## Goal

Make match-list sync actions operate on the user's current filtered match set, with per-match fallback actions and expandable result details for successful, failed, and skipped matches.

## User-Facing Behavior

- Remove independent day-count inputs from the match-list sync strip.
- The top-level `同步赛程/赛果` and `同步赔率` buttons use the full active filter set: start time, end time, league, status, odds availability, and search.
- The backend resolves the target matches from those filters rather than relying on the first visible page only.
- Each match row has single-match actions for `赛果` and `赔率`; clicking them syncs only that match.
- Sync results show totals and expandable groups for success, failed, and skipped items. Each expanded row identifies the match and includes the reason or count details.

## Backend Design

- Reuse the match-list filtering rules in `match_list_workspace_service.py` to select target `Match` rows for sync.
- Introduce structured result dataclasses:
  - `MatchSyncItem`: match id, kickoff time, league/team display fields, status, message, created/updated/skipped/request counters.
  - `MatchSyncReport`: sync type, started/finished timestamps, target count, totals, and grouped items.
- Add Web routes:
  - `POST /api/match-list/sync/fixtures-results`
  - `POST /api/match-list/sync/odds`
  - `POST /api/matches/{match_id}/sync/fixtures-results`
  - `POST /api/matches/{match_id}/sync/odds`
- Bulk routes accept filter payloads. Single routes accept no filter payload beyond the path match id.
- Fixtures/results sync should refresh existing matches by API-Football fixture id where possible and classify matches without source fixture ids as skipped.
- Odds sync should use the OddsPapi historical odds path with `match_ids`, so the match-list page sees updated `historical_odds_snapshots`.

## Frontend Design

- Keep freshness cards, but replace day inputs with two batch buttons and a target-count label.
- Add a result panel under the sync strip after any sync action.
- Use `<details>` sections for `成功`, `失败`, and `跳过`, with match rows inside each section.
- Add row-level action buttons in the match table. Button clicks must stop row navigation before running the sync.
- Refresh the match-list workspace after a sync completes so status, score, and odds summaries update.

## Error Handling

- Batch sync is partial-success oriented: one failed match does not fail the whole batch.
- Transport or configuration errors that prevent all work should still return an HTTP error and create a failed `DataSyncRun`.
- Per-match failures are included in the `failed` group with the raw error message trimmed for display.

## Testing

- Backend tests cover filter-to-target resolution, grouped sync report payloads, and single-match routes.
- Frontend tests cover API payload shape and summary helper behavior.
- Existing match-list workspace tests remain the regression net for filtering semantics.

# Match List And Sync Design

## Context

The Web console can currently view odds trends, worker status, and paper
recommendation tracking, but it does not provide buttons for syncing recent
fixtures/results or recent odds. Those operations exist in the CLI/service layer:

- `sync upcoming --days`
- `sync odds --days`

The new Web page should be a match list first. Sync controls and freshness
signals are supporting tools, not the page's main content.

## Decisions

- Add a dedicated navigation page named `比赛列表`.
- The page defaults to matches from now through the next `24` hours.
- The page can browse all local matches by changing the time range.
- Add two required sync actions:
  - `同步近期赛程/赛果`, default `3` days.
  - `同步近期赔率`, default `2` days.
- Do not add a combined `同步赛果并结算纸面记录` button.
- Add a lightweight `data_sync_runs` table so the page can show the latest
  successful sync run time.
- Keep the top freshness/sync area compact. The list is the primary visual area.
- Match details are not a permanent right-side panel. Clicking a match opens a
  dedicated match detail page at `/matches/:id`.

## Data Freshness

Create `data_sync_runs` with fields:

- `id`
- `sync_type`: `fixtures_results` or `odds`
- `started_at`
- `finished_at`
- `status`: `running`, `success`, `failed`
- `days`
- `created_count`
- `updated_count`
- `skipped_count`
- `requests_used`
- `error_message`

The page freshness cards show:

- Latest successful `fixtures_results` sync time.
- Latest successful `odds` sync time.
- Local latest kickoff time as supporting context.
- Local latest odds snapshot time as supporting context.

All displayed times use Beijing time.

## Match List Page

Route/view: `比赛列表`.

Top compact toolbar:

- Freshness chips/cards:
  - `赛程/赛果同步`: latest successful sync time and default days.
  - `赔率同步`: latest successful sync time and default days.
- Numeric inputs or compact controls for days:
  - Fixtures/results default `3`.
  - Odds default `2`.
- Buttons:
  - `同步赛程/赛果`
  - `同步赔率`

Main filters:

- Time range:
  - Default: next `24` hours.
  - Presets: next 24h, next 3d, previous 24h, previous 7d, all.
  - Custom range can be added later if needed.
- League filter.
- Status filter:
  - all
  - not_started
  - live
  - finished
- Odds filter:
  - all
  - with_odds
  - without_odds
- Team search.

Main list columns:

- Beijing kickoff time.
- League display name.
- Home team display name with logo if available.
- Away team display name with logo if available.
- Status and score if available.
- Odds availability.
- Core odds summary if available:
  - Asian handicap first, using explicit language like `客队 +0.50 @ 1.930`.
  - Total goals and match winner can be compact secondary fields.

The list should use local database data only. Sync buttons update the database,
then refresh the workspace payload.

## Match Detail Page

Route: `/matches/:id`.

The first implementation can be inside the existing single-page dashboard state
rather than a full router, but the conceptual route and payload should be
designed as match detail by id.

Detail sections:

- Header:
  - League display name.
  - Beijing kickoff time.
  - Status and score.
  - Home/away team display names and logos.
- Team data:
  - Show currently available local fields.
  - If richer team metrics are not available, display `待接入`.
- Odds:
  - Latest Asian handicap, total goals, and match winner if synchronized.
  - Link or action back to existing odds trend view for the same match.
- Recommendation summary placeholder:
  - Paper recommendations: show count/status if present, otherwise `暂无纸面推荐记录`.
  - Formal recommendations: show count/status if present, otherwise `暂无正式推荐记录`.
  - Leave a stable payload shape for future links to paper tracking and formal
    recommendation records.

## API

Add endpoints:

- `GET /api/match-list/workspace`
  - Query parameters: time preset/range, league id/name, status, odds filter,
    search text, limit/offset.
  - Returns freshness metadata, filter options, and match rows.
- `POST /api/match-list/sync/fixtures-results`
  - Body: `{ "days": 3 }`
  - Runs the existing upcoming/results style sync for the selected recent window.
  - Records a `data_sync_runs` row.
  - Returns the refreshed workspace payload or a sync result plus enough metadata
    for the frontend to refresh.
- `POST /api/match-list/sync/odds`
  - Body: `{ "days": 2 }`
  - Runs the existing `run_sync_odds` path.
  - Records a `data_sync_runs` row.
- `GET /api/matches/{match_id}/detail`
  - Returns the match detail payload.

Implementation detail for `fixtures-results`: the existing CLI separates
`upcoming` and `results`. The Web action should be named `同步赛程/赛果` and may
call the same provider path needed to update upcoming fixtures and recent result
statuses for the configured days. If needed, v1 can call `run_sync_upcoming(days)`
and a recent `run_sync_results` window under one recorded run.

## Error Handling

- Sync buttons show running, success, and failed states.
- Failed sync runs are recorded with `status=failed` and `error_message`.
- If a sync fails, existing match list data remains visible.
- The odds sync button should surface failed fixture id and provider error when
  available.
- Detail page returns a clear not-found state for missing match ids.

## Testing

Backend tests:

- `data_sync_runs` model/schema creation.
- Creating success and failed sync run records.
- Workspace freshness uses the latest successful run per sync type.
- Match list default window is now to next 24h.
- League/status/odds/search filters.
- Match row includes Chinese names, logos, status, score, and odds summary.
- Sync endpoints call injected sync runners and record run results.
- Match detail payload includes team logos, odds summaries, and recommendation
  placeholder fields.

Frontend tests:

- Workspace helper builds freshness cards.
- Default filter state is next 24h.
- Match row formatting uses Chinese names and explicit Asian handicap text.
- Filter helpers classify not started/live/finished and with/without odds.
- Detail helper handles missing team data with `待接入`.

Verification:

- Focused pytest for match list service/API.
- Focused Vitest for match list workspace helpers.
- `npm run build`.

## Out Of Scope

- Combined sync-and-settle button.
- Full custom date-range picker if presets are enough for v1.
- Rich team analytics beyond currently available local fields.
- Recommendation detail navigation implementation beyond stable placeholders.

# Paper Recommendation Tracking Design

## Context

The project has completed the Asian handicap observation model v1 and the paper
queue. The current queue can score upcoming matches and expose candidates through
CLI and `/api/paper-recommendations/queue`.

This design adds a dedicated paper tracking workflow for observation-period
recommendations. It must not pollute formal recommendation records. User-facing
display must use Beijing time, Chinese league/team names when configured, and
explicit Asian handicap wording such as `客队 +0.50`.

## Decisions

- Add an independent Web page named `纸面跟踪`.
- Use a dedicated table, `paper_recommendation_records`.
- Use a semi-automatic workflow: candidates are shown first; the user records
  observations manually or with a batch action.
- The table is strategy-agnostic. v1 only opens one strategy:
  - Display name: `亚盘客队方向 · HGB边际 v1`
  - Strategy key: `asian_away_cover_hgb_edge_v1`
  - Rule: `market_type=asian_handicap`, `side=away_cover`, `edge >= 0.10`
- Future paper-direct or formal strategies can use the same table with their own
  Chinese display name and stable strategy key.
- Record-time market line and odds are locked by default. The user can manually
  edit line, odds, and notes later.

## Data Model

Create `paper_recommendation_records` with fields for:

- Match identity: `match_id`, source match id if useful, league/team snapshots,
  kickoff time.
- Strategy identity: `strategy_key`, `strategy_display_name`, `model_name`,
  optional `signal_version`.
- Recommendation: `market_type`, `side`, `recommended_handicap`,
  `line_bucket`, `risk_tags`.
- Original market snapshot: `original_market_line`, `original_odds`.
- Current market snapshot: `current_market_line`, `current_odds`.
- Scoring: `model_probability`, `market_probability`, `edge`.
- Tracking: `stake_units`, `status`, `created_at`, `updated_at`.
- Manual adjustment: `is_manually_adjusted`, `manual_note`.
- Settlement: `settlement_result`, `profit_units`, `settled_at`.

Default `stake_units` is `1.00`. `current_market_line/current_odds` initially
equal `original_market_line/original_odds`.

Deduplication: the same `match_id + strategy_key + market_type + side` cannot
create more than one active paper record. `void` records are not active.

## Display Rules

- All timestamps shown in the Web console and reports are Beijing time.
- League and team names use configured Chinese display names when available.
- Strategy display prioritizes Chinese names. English keys remain visible as
  secondary/debug fields.
- Asian handicap display converts from the stored home-team perspective:
  - `side=away_cover`, `market_line=-0.50` displays as `客队 +0.50`.
  - `side=away_cover`, `market_line=+0.25` displays as `客队 -0.25`.
  - `side=home_cover`, `market_line=-0.25` displays as `主队 -0.25`.

## API

Add paper tracking endpoints:

- `GET /api/paper-recommendations/workspace`
  - Returns candidate queue, recorded paper records, summary metrics, and
    available strategies.
- `POST /api/paper-recommendations/records`
  - Creates a paper record from a queue candidate.
  - v1 only accepts candidates for `亚盘客队方向 · HGB边际 v1`.
- `PATCH /api/paper-recommendations/records/{id}`
  - Edits current line, current odds, and note for pending/unsettled records.
  - Marks the record as manually adjusted.
- `POST /api/paper-recommendations/settle`
  - Settles pending records whose matches have final scores.
- `POST /api/paper-recommendations/records/{id}/void`
  - Voids an erroneous record so it is excluded from ROI.

Status values:

- `pending`: recorded and waiting for a result.
- `settled`: settled with result and profit.
- `void`: manually excluded.
- `unsettleable`: match appears complete but lacks data needed to settle.

Settlement result values reuse the existing vocabulary:
`win`, `half_win`, `push`, `half_loss`, `loss`.

## Settlement

v1 reuses existing settlement functions:

- `settle_asian_handicap`
- `profit_units_for_result`

Settlement uses `current_market_line/current_odds`, not the original values.
This allows manual correction while preserving the original recommendation
snapshot for review.

Settled ROI excludes `void` and `unsettleable` records. Reports should expose a
split between unadjusted and manually adjusted records so model signal quality is
not confused with operator correction.

## Web Page

Add a new navigation item: `纸面跟踪`.

The page contains:

- Summary cards: candidates, recorded records, pending records, hit rate, ROI.
- Candidate queue:
  - Shows eligible upcoming candidates.
  - Main display: strategy Chinese name, fixture, `客队 +0.50 @ 1.930`,
    model probability, market probability, edge, line bucket, risk tags.
  - Actions: refresh queue, record observation, batch record eligible candidates.
- Paper record table:
  - Shows recorded time, kickoff time, league, fixture, strategy, handicap,
    odds, edge, status, settlement result, profit, manual-adjusted flag.
  - Actions: edit line/odds/note, void.
- Review summary:
  - Groups by strategy, league, line bucket, settlement result, and manual
    adjustment flag.

## Error Handling

- Candidates without odds or without `candidate` status cannot be recorded.
- Duplicate active records are rejected and surfaced as a clear API error.
- Pending records can be edited. Settled records are not editable in v1.
- Missing final scores keep records pending. If the match is finished but cannot
  be settled due missing data, mark or report `unsettleable`.
- API responses should make skipped settlement records visible.

## Testing

Python service tests:

- Create a paper record from a valid candidate.
- Reject invalid/non-candidate rows.
- Reject duplicate active records.
- Lock original line/odds at record time.
- Mark manual edits and preserve original line/odds.
- Settle Asian handicap results across win, half win, push, half loss, and loss.
- Build ROI and grouped summaries.

Web API tests:

- Workspace includes candidates, records, summaries, and strategy metadata.
- Record, edit, settle, and void endpoints work.
- Payloads include Chinese display names, Beijing-time timestamps, and explicit
  recommended handicap strings.

Frontend tests:

- Workspace transformation and summary cards.
- Candidate button enabled/disabled states.
- Paper record edit state.
- Grouped review summaries.

Verification:

- Run focused pytest tests for paper tracking and Web API.
- Run focused frontend tests.
- Run `npm run build`.

## Out Of Scope

- Automatic recording on every refresh.
- Full edit audit history and rollback.
- Formal recommendation promotion workflow.
- New model training or threshold changes.

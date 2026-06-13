# Match List Dynamic League Filter Design

## Goal

On the match list page, the league dropdown should reflect the current time range instead of showing every league in the database. When the user changes the start or end time, the selected league resets to "all leagues" and the dropdown is repopulated with leagues that have matches in the new time window.

## Behavior

- The time range is the upstream filter for league choices.
- Changing `start_time` or `end_time` clears `league_name`.
- The league dropdown lists distinct leagues that have at least one match in the active time window.
- The visible match table still applies the selected league, status, odds, and search filters.
- League option labels continue to use `DisplayNameService.display_league()`.
- League options are computed from the full filtered time window, not from the visible `limit`, so options are not lost when more than 200 matches exist.

## Architecture

Backend `build_match_list_workspace()` already computes the active time window. It will call a revised `_league_options()` that accepts `start` and `end` and queries distinct leagues from matches inside that window.

Frontend `FilteredMatchListView` already routes filter updates through `onFiltersChange`. The two datetime inputs will include `league_name: ""` in their change payloads so a new time range starts from all leagues.

## Testing

- Add a backend service test proving `workspace.leagues` only includes leagues with matches inside the requested time window.
- Add a frontend helper test for time-filter change payloads so both start and end changes clear `league_name`.
- Run focused backend and frontend tests.

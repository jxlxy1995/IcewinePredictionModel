# Debug Database Handoff

This note is for sharing a local debug database with an external reviewer without
committing the database into Git.

## Code Baseline

- Repository commit: `3524eb6`
- Local database path expected by the app: `local_data/icewine_prediction.sqlite3`
- Prepared archive path: `local_data/icewine_prediction_20260601.zip`

## Restore Steps

1. Clone or update the repository to commit `3524eb6`.
2. Download the database archive from the private attachment or shared drive.
3. Extract `icewine_prediction.sqlite3` into `local_data/`.
4. Confirm the final path is:

```text
local_data/icewine_prediction.sqlite3
```

5. Start the app or run the relevant tests/scripts against the restored local
   database.

## Useful Checks

```powershell
git status --short --ignored local_data/icewine_prediction.sqlite3
Get-Item local_data/icewine_prediction.sqlite3
```

The first command should show the database as ignored. The database must remain
outside Git history.

## Review Context

The database contains the current local match, odds, historical odds, training,
and paper recommendation state used for debugging:

- match list odds status filtering and refresh behavior
- OddsPapi pre-kickoff and post-match odds refresh/backfill behavior
- paper recommendation replay for finished matches
- paper candidate settlement simulation and strategy signal inspection

## Safety Notes

- Do not commit `local_data/`, `*.sqlite3`, `*.sqlite`, `*.db`, or generated zip
  archives.
- Share the archive only through a private channel.
- If the database is updated locally, create a new dated archive instead of
  replacing Git-tracked files.

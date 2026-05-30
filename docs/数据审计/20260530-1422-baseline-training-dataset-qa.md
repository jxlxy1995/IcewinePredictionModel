# Baseline Training Dataset QA

- CSV: `local_data\training\baseline_main_leagues_20260530-1422.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Columns | 42 |
| Empty required cells | 0 |
| Invalid odds cells | 0 |
| Invalid probability cells | 0 |
| Invalid overround cells | 0 |
| Thin-history rows | 152 (0.0285) |

## Overround Ranges

| Market | Min | Max |
| --- | ---: | ---: |
| asian_handicap | 1.0090 | 1.0786 |
| total_goals | 1.0140 | 1.0922 |
| match_winner | 1.0171 | 1.1057 |

## Result Labels

| Label | Count |
| --- | ---: |
| away_win | 1601 |
| home_win | 2325 |
| draw | 1404 |

### asian_handicap_home_result

| Label | Count |
| --- | ---: |
| loss | 2041 |
| win | 2129 |
| push | 402 |
| half_loss | 434 |
| half_win | 324 |

### asian_handicap_away_result

| Label | Count |
| --- | ---: |
| win | 2041 |
| loss | 2129 |
| push | 402 |
| half_win | 434 |
| half_loss | 324 |

### total_goals_over_result

| Label | Count |
| --- | ---: |
| half_loss | 392 |
| push | 262 |
| win | 2226 |
| loss | 2141 |
| half_win | 309 |

### total_goals_under_result

| Label | Count |
| --- | ---: |
| half_win | 392 |
| push | 262 |
| loss | 2226 |
| win | 2141 |
| half_loss | 309 |

### match_winner_home_result

| Label | Count |
| --- | ---: |
| loss | 3005 |
| win | 2325 |

### match_winner_draw_result

| Label | Count |
| --- | ---: |
| loss | 3926 |
| win | 1404 |

### match_winner_away_result

| Label | Count |
| --- | ---: |
| win | 1601 |
| loss | 3729 |

## By Season

| Season | Rows |
| --- | ---: |
| 2025 | 3707 |
| 2026 | 1623 |

## By Month

| Month | Rows |
| --- | ---: |
| 2026-01 | 200 |
| 2026-02 | 1051 |
| 2026-03 | 1227 |
| 2026-04 | 1588 |
| 2026-05 | 1264 |

## Low Sample Leagues

| League | Rows |
| --- | ---: |
| Ykkösliiga (Finland) | 29 |

## Top Asian Handicap Lines

| Line | Rows |
| --- | ---: |
| -0.25 | 1062 |
| -0.50 | 765 |
| 0.00 | 748 |
| 0.25 | 577 |
| -0.75 | 526 |
| -1.00 | 373 |
| 0.50 | 341 |
| -1.25 | 250 |
| 0.75 | 177 |
| -1.50 | 117 |
| 1.00 | 115 |
| -1.75 | 77 |
| 1.25 | 52 |
| -2.00 | 38 |
| 1.50 | 33 |
| -2.25 | 23 |
| 1.75 | 17 |
| -2.50 | 13 |
| 2.00 | 9 |
| -2.75 | 7 |

## Top Total Goals Lines

| Line | Rows |
| --- | ---: |
| 2.50 | 1256 |
| 2.25 | 1087 |
| 2.75 | 1046 |
| 3.00 | 693 |
| 3.25 | 428 |
| 2.00 | 369 |
| 3.50 | 184 |
| 1.75 | 144 |
| 3.75 | 70 |
| 1.50 | 23 |
| 4.25 | 13 |
| 4.00 | 12 |
| 4.75 | 3 |
| 4.50 | 2 |

## Snapshot Count Ranges

| Field | Min | Max |
| --- | ---: | ---: |
| asian_handicap_snapshot_count | 2 | 50 |
| total_goals_snapshot_count | 2 | 50 |
| match_winner_snapshot_count | 3 | 51 |

## Validation Details

- Empty required cells: -
- Invalid odds cells: -
- Invalid probability cells: -
- Invalid overround cells: -

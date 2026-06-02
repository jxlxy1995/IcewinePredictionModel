# Baseline Home Cover Signal Research

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260602-2036.csv`
- Scope: `asian_handicap raw_hgb_team_form_plus_all_markets home_cover`
- Workflow: research only; no paper strategy registration

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5583 |
| Folds | 5 |
| Train ratio | 0.6000 |
| Validation ratio | 0.1000 |
| Thresholds | 0.0600, 0.0800, 0.1000, 0.1200, 0.1500, 0.1800, 0.2000 |

## Rating Counts

| Rating | Candidates |
| --- | ---: |
| promotable | 7 |
| watchlist | 9 |
| rejected | 5 |

## Candidate Grid

| Line bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI | Positive ROI folds | Worst fold ROI |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| home_favorite | 0.1500 | promotable | 320 | 183 | 0.5719 | 40.7980 | 0.1275 | 4 | -0.0609 |
| home_favorite | 0.1200 | promotable | 386 | 221 | 0.5725 | 48.9370 | 0.1268 | 4 | -0.0874 |
| home_favorite | 0.1800 | promotable | 266 | 150 | 0.5639 | 29.9540 | 0.1126 | 4 | -0.1749 |
| home_favorite | 0.0800 | promotable | 486 | 275 | 0.5658 | 54.6330 | 0.1124 | 4 | -0.0706 |
| home_favorite | 0.1000 | promotable | 442 | 249 | 0.5633 | 47.5560 | 0.1076 | 4 | -0.0987 |
| home_favorite | 0.2000 | promotable | 219 | 122 | 0.5571 | 21.6550 | 0.0989 | 4 | -0.1228 |
| home_favorite | 0.0600 | promotable | 559 | 307 | 0.5492 | 44.1600 | 0.0790 | 4 | -0.0718 |
| home_underdog | 0.2000 | watchlist | 83 | 49 | 0.5904 | 11.6740 | 0.1407 | 4 | -0.2417 |
| home_underdog | 0.1800 | watchlist | 106 | 59 | 0.5566 | 7.3950 | 0.0698 | 3 | -0.2463 |
| pickem | 0.1200 | watchlist | 79 | 43 | 0.5443 | 3.9560 | 0.0501 | 4 | -0.2384 |
| pickem | 0.0600 | watchlist | 106 | 57 | 0.5377 | 4.6820 | 0.0442 | 3 | -0.2941 |
| home_underdog | 0.1200 | watchlist | 157 | 85 | 0.5414 | 6.2360 | 0.0397 | 2 | -0.2612 |
| pickem | 0.1500 | watchlist | 65 | 35 | 0.5385 | 2.4520 | 0.0377 | 3 | -0.1043 |
| home_underdog | 0.1000 | watchlist | 169 | 91 | 0.5385 | 5.8160 | 0.0344 | 2 | -0.2343 |
| pickem | 0.0800 | watchlist | 96 | 51 | 0.5313 | 2.9640 | 0.0309 | 3 | -0.2499 |
| home_underdog | 0.1500 | watchlist | 133 | 71 | 0.5338 | 3.3560 | 0.0252 | 3 | -0.2601 |
| pickem | 0.1000 | rejected | 91 | 47 | 0.5165 | -0.1510 | -0.0017 | 3 | -0.3399 |
| pickem | 0.1800 | rejected | 53 | 27 | 0.5094 | -0.7740 | -0.0146 | 3 | -0.1383 |
| home_underdog | 0.0800 | rejected | 187 | 96 | 0.5134 | -2.7320 | -0.0146 | 2 | -0.2607 |
| home_underdog | 0.0600 | rejected | 196 | 98 | 0.5000 | -7.8010 | -0.0398 | 1 | -0.2853 |
| pickem | 0.2000 | rejected | 48 | 23 | 0.4792 | -3.4750 | -0.0724 | 2 | -0.3053 |

## Line Bucket Overview

| Line bucket | Bets | Best rating | Best threshold | Best ROI | Best positive ROI folds |
| --- | ---: | --- | ---: | ---: | ---: |
| home_favorite | 559 | promotable | 0.1500 | 0.1275 | 4 |
| home_underdog | 196 | watchlist | 0.2000 | 0.1407 | 4 |
| pickem | 106 | watchlist | 0.1200 | 0.0501 | 4 |

## Promotion Recommendation

Promotable candidates:
- `home_favorite` at `0.1500`: ROI 0.1275, 4/5 positive folds.
- `home_favorite` at `0.1200`: ROI 0.1268, 4/5 positive folds.
- `home_favorite` at `0.1800`: ROI 0.1126, 4/5 positive folds.
- `home_favorite` at `0.0800`: ROI 0.1124, 4/5 positive folds.
- `home_favorite` at `0.1000`: ROI 0.1076, 4/5 positive folds.
- `home_favorite` at `0.2000`: ROI 0.0989, 4/5 positive folds.
- `home_favorite` at `0.0600`: ROI 0.0790, 4/5 positive folds.

Watchlist candidates:
- `home_underdog` at `0.2000`: ROI 0.1407, 4/5 positive folds.
- `home_underdog` at `0.1800`: ROI 0.0698, 3/5 positive folds.
- `pickem` at `0.1200`: ROI 0.0501, 4/5 positive folds.
- `pickem` at `0.0600`: ROI 0.0442, 3/5 positive folds.
- `home_underdog` at `0.1200`: ROI 0.0397, 2/5 positive folds.
- `pickem` at `0.1500`: ROI 0.0377, 3/5 positive folds.
- `home_underdog` at `0.1000`: ROI 0.0344, 2/5 positive folds.
- `pickem` at `0.0800`: ROI 0.0309, 3/5 positive folds.
- `home_underdog` at `0.1500`: ROI 0.0252, 3/5 positive folds.

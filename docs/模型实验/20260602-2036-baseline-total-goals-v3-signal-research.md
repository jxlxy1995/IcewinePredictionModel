# Baseline Total Goals v3 Signal Research

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260602-2036.csv`
- Scope: `total_goals raw_hgb_team_form_plus_all_markets`
- Workflow: research only; no paper strategy registration

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5583 |
| Folds | 5 |
| Train ratio | 0.6000 |
| Validation ratio | 0.1000 |
| Thresholds | 0.0600, 0.0800, 0.1000, 0.1200, 0.1500, 0.1800, 0.2000 |
| Baseline v2 bets | 273 |
| Baseline v2 profit | 40.0900 |
| Baseline v2 ROI | 0.1468 |

## Rating Counts

| Rating | Candidates |
| --- | ---: |
| promotable | 15 |
| watchlist | 15 |
| rejected | 26 |

## Candidate Grid

| Side bucket | Threshold | Rating | Bets | Wins | Hit rate | Profit | ROI | Positive ROI folds | Worst fold ROI | Overlap | Overlap share | Incremental bets | Incremental ROI |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| under@mid_2.75 | 0.1800 | promotable | 78 | 51 | 0.6538 | 20.5100 | 0.2629 | 5 | 0.1589 | 78 | 1.0000 | 0 | - |
| under@mid_2.75 | 0.2000 | promotable | 60 | 39 | 0.6500 | 15.3630 | 0.2561 | 5 | 0.1081 | 60 | 1.0000 | 0 | - |
| under@mid_2.75 | 0.1200 | promotable | 139 | 85 | 0.6115 | 25.5780 | 0.1840 | 5 | 0.1162 | 139 | 1.0000 | 0 | - |
| under@mid_2.75 | 0.1500 | promotable | 100 | 61 | 0.6100 | 18.1950 | 0.1820 | 5 | 0.0807 | 100 | 1.0000 | 0 | - |
| over@mid_2.75 | 0.0600 | promotable | 101 | 62 | 0.6139 | 17.9070 | 0.1773 | 4 | -0.0747 | 83 | 0.8218 | 18 | 0.3904 |
| under@mid_2.75 | 0.1000 | promotable | 166 | 100 | 0.6024 | 27.7730 | 0.1673 | 5 | 0.1371 | 166 | 1.0000 | 0 | - |
| under@mid_2.75 | 0.0600 | promotable | 209 | 125 | 0.5981 | 33.3930 | 0.1598 | 5 | 0.1029 | 190 | 0.9091 | 19 | 0.2202 |
| under@mid_2.75 | 0.0800 | promotable | 190 | 113 | 0.5947 | 29.2100 | 0.1537 | 5 | 0.0848 | 190 | 1.0000 | 0 | - |
| over@low_<=2.25 | 0.0600 | promotable | 163 | 97 | 0.5951 | 24.0310 | 0.1474 | 4 | -0.0920 | 0 | 0.0000 | 163 | 0.1474 |
| over@mid_2.75 | 0.0800 | promotable | 83 | 49 | 0.5904 | 10.8800 | 0.1311 | 4 | -0.0817 | 83 | 1.0000 | 0 | - |
| over@low_<=2.25 | 0.1000 | promotable | 141 | 82 | 0.5816 | 17.0660 | 0.1210 | 4 | -0.1782 | 0 | 0.0000 | 141 | 0.1210 |
| over@mid_2.50 | 0.2000 | promotable | 66 | 38 | 0.5758 | 7.1990 | 0.1091 | 4 | -0.1225 | 0 | 0.0000 | 66 | 0.1091 |
| over@mid_2.75 | 0.1000 | promotable | 76 | 44 | 0.5789 | 8.2350 | 0.1084 | 4 | -0.0307 | 76 | 1.0000 | 0 | - |
| under@low_<=2.25 | 0.1200 | promotable | 136 | 74 | 0.5441 | 8.2940 | 0.0610 | 4 | -0.0305 | 0 | 0.0000 | 136 | 0.0610 |
| under@low_<=2.25 | 0.1000 | promotable | 148 | 80 | 0.5405 | 8.1450 | 0.0550 | 4 | -0.0986 | 0 | 0.0000 | 148 | 0.0550 |
| over@low_<=2.25 | 0.0800 | watchlist | 151 | 87 | 0.5762 | 16.8870 | 0.1118 | 3 | -0.1277 | 0 | 0.0000 | 151 | 0.1118 |
| over@mid_2.50 | 0.1200 | watchlist | 150 | 84 | 0.5600 | 11.6030 | 0.0774 | 4 | -0.2970 | 0 | 0.0000 | 150 | 0.0774 |
| over@low_<=2.25 | 0.1200 | watchlist | 120 | 67 | 0.5583 | 9.0800 | 0.0757 | 3 | -0.2050 | 0 | 0.0000 | 120 | 0.0757 |
| over@mid_2.75 | 0.1200 | watchlist | 66 | 37 | 0.5606 | 4.9720 | 0.0753 | 3 | -0.0835 | 66 | 1.0000 | 0 | - |
| over@mid_2.50 | 0.1000 | watchlist | 177 | 97 | 0.5480 | 9.9160 | 0.0560 | 3 | -0.3811 | 0 | 0.0000 | 177 | 0.0560 |
| over@mid_2.50 | 0.0600 | watchlist | 230 | 124 | 0.5391 | 9.9130 | 0.0431 | 3 | -0.2988 | 0 | 0.0000 | 230 | 0.0431 |
| over@mid_2.50 | 0.0800 | watchlist | 208 | 112 | 0.5385 | 8.3350 | 0.0401 | 3 | -0.3778 | 0 | 0.0000 | 208 | 0.0401 |
| over@mid_2.50 | 0.1500 | watchlist | 113 | 61 | 0.5398 | 4.4910 | 0.0397 | 4 | -0.2267 | 0 | 0.0000 | 113 | 0.0397 |
| under@high_>=3.00 | 0.1800 | watchlist | 143 | 77 | 0.5385 | 5.2900 | 0.0370 | 2 | -0.1013 | 0 | 0.0000 | 143 | 0.0370 |
| under@low_<=2.25 | 0.1500 | watchlist | 109 | 57 | 0.5229 | 2.8090 | 0.0258 | 2 | -0.1311 | 0 | 0.0000 | 109 | 0.0258 |
| under@high_>=3.00 | 0.2000 | watchlist | 122 | 65 | 0.5328 | 3.0350 | 0.0249 | 1 | -0.0673 | 0 | 0.0000 | 122 | 0.0249 |
| over@high_>=3.00 | 0.2000 | watchlist | 63 | 33 | 0.5238 | 0.4450 | 0.0071 | 2 | -1.0000 | 0 | 0.0000 | 63 | 0.0071 |
| under@mid_2.50 | 0.1000 | watchlist | 189 | 99 | 0.5238 | 1.1690 | 0.0062 | 3 | -0.1770 | 0 | 0.0000 | 189 | 0.0062 |
| under@low_<=2.25 | 0.2000 | watchlist | 72 | 37 | 0.5139 | 0.3710 | 0.0052 | 1 | -0.2459 | 0 | 0.0000 | 72 | 0.0052 |
| under@mid_2.50 | 0.1200 | watchlist | 165 | 86 | 0.5212 | 0.2110 | 0.0013 | 3 | -0.1288 | 0 | 0.0000 | 165 | 0.0013 |
| over@low_<=2.25 | 0.1500 | rejected | 92 | 48 | 0.5217 | -0.0400 | -0.0004 | 2 | -0.2896 | 0 | 0.0000 | 92 | -0.0004 |
| under@low_<=2.25 | 0.0800 | rejected | 166 | 85 | 0.5120 | -0.1060 | -0.0006 | 3 | -0.1792 | 0 | 0.0000 | 166 | -0.0006 |
| over@mid_2.50 | 0.1800 | rejected | 83 | 43 | 0.5181 | -0.2440 | -0.0029 | 3 | -0.2292 | 0 | 0.0000 | 83 | -0.0029 |
| under@mid_2.50 | 0.0800 | rejected | 220 | 114 | 0.5182 | -0.9940 | -0.0045 | 2 | -0.1771 | 0 | 0.0000 | 220 | -0.0045 |
| over@high_>=3.00 | 0.1800 | rejected | 79 | 41 | 0.5190 | -0.4820 | -0.0061 | 2 | -1.0000 | 0 | 0.0000 | 79 | -0.0061 |
| under@low_<=2.25 | 0.0600 | rejected | 187 | 95 | 0.5080 | -1.2140 | -0.0065 | 3 | -0.1908 | 0 | 0.0000 | 187 | -0.0065 |
| over@high_>=3.00 | 0.1500 | rejected | 101 | 52 | 0.5149 | -0.9910 | -0.0098 | 2 | -0.4240 | 0 | 0.0000 | 101 | -0.0098 |
| under@high_>=3.00 | 0.1500 | rejected | 193 | 98 | 0.5078 | -4.4320 | -0.0230 | 2 | -0.2374 | 0 | 0.0000 | 193 | -0.0230 |
| under@low_<=2.25 | 0.1800 | rejected | 82 | 41 | 0.5000 | -1.9050 | -0.0232 | 2 | -0.2998 | 0 | 0.0000 | 82 | -0.0232 |
| under@high_>=3.00 | 0.1000 | rejected | 280 | 141 | 0.5036 | -9.4150 | -0.0336 | 1 | -0.1694 | 0 | 0.0000 | 280 | -0.0336 |
| under@high_>=3.00 | 0.0800 | rejected | 313 | 157 | 0.5016 | -11.7280 | -0.0375 | 2 | -0.1544 | 0 | 0.0000 | 313 | -0.0375 |
| under@high_>=3.00 | 0.1200 | rejected | 243 | 121 | 0.4979 | -10.1310 | -0.0417 | 2 | -0.2093 | 0 | 0.0000 | 243 | -0.0417 |
| over@high_>=3.00 | 0.1200 | rejected | 133 | 66 | 0.4962 | -5.7130 | -0.0430 | 3 | -0.4882 | 0 | 0.0000 | 133 | -0.0430 |
| over@high_>=3.00 | 0.1000 | rejected | 154 | 76 | 0.4935 | -6.6800 | -0.0434 | 2 | -0.3715 | 0 | 0.0000 | 154 | -0.0434 |
| over@mid_2.75 | 0.1500 | rejected | 52 | 26 | 0.5000 | -2.2840 | -0.0439 | 1 | -1.0000 | 52 | 1.0000 | 0 | - |
| over@mid_2.75 | 0.1800 | rejected | 34 | 17 | 0.5000 | -1.4920 | -0.0439 | 1 | -1.0000 | 34 | 1.0000 | 0 | - |
| under@high_>=3.00 | 0.0600 | rejected | 345 | 172 | 0.4986 | -15.2220 | -0.0441 | 3 | -0.1495 | 0 | 0.0000 | 345 | -0.0441 |
| over@mid_2.75 | 0.2000 | rejected | 28 | 14 | 0.5000 | -1.2500 | -0.0446 | 2 | -1.0000 | 28 | 1.0000 | 0 | - |
| under@mid_2.50 | 0.0600 | rejected | 252 | 125 | 0.4960 | -12.0870 | -0.0480 | 2 | -0.2001 | 0 | 0.0000 | 252 | -0.0480 |
| over@low_<=2.25 | 0.1800 | rejected | 79 | 39 | 0.4937 | -4.2520 | -0.0538 | 2 | -0.2252 | 0 | 0.0000 | 79 | -0.0538 |
| over@high_>=3.00 | 0.0600 | rejected | 216 | 104 | 0.4815 | -14.3160 | -0.0663 | 3 | -0.3832 | 0 | 0.0000 | 216 | -0.0663 |
| over@high_>=3.00 | 0.0800 | rejected | 189 | 91 | 0.4815 | -12.6870 | -0.0671 | 1 | -0.3036 | 0 | 0.0000 | 189 | -0.0671 |
| under@mid_2.50 | 0.1500 | rejected | 134 | 65 | 0.4851 | -9.0560 | -0.0676 | 2 | -0.2625 | 0 | 0.0000 | 134 | -0.0676 |
| under@mid_2.50 | 0.2000 | rejected | 76 | 36 | 0.4737 | -6.7800 | -0.0892 | 2 | -0.3607 | 0 | 0.0000 | 76 | -0.0892 |
| under@mid_2.50 | 0.1800 | rejected | 98 | 46 | 0.4694 | -9.5260 | -0.0972 | 2 | -0.2874 | 0 | 0.0000 | 98 | -0.0972 |
| over@low_<=2.25 | 0.2000 | rejected | 66 | 31 | 0.4697 | -6.5150 | -0.0987 | 1 | -0.2299 | 0 | 0.0000 | 66 | -0.0987 |

## Side Bucket Overview

| Side bucket | Bets | Best rating | Best threshold | Best ROI | Best positive ROI folds |
| --- | ---: | --- | ---: | ---: | ---: |
| over@high_>=3.00 | 216 | watchlist | 0.2000 | 0.0071 | 2 |
| over@low_<=2.25 | 163 | promotable | 0.0600 | 0.1474 | 4 |
| over@mid_2.50 | 230 | promotable | 0.2000 | 0.1091 | 4 |
| over@mid_2.75 | 101 | promotable | 0.0600 | 0.1773 | 4 |
| under@high_>=3.00 | 345 | watchlist | 0.1800 | 0.0370 | 2 |
| under@low_<=2.25 | 187 | promotable | 0.1200 | 0.0610 | 4 |
| under@mid_2.50 | 252 | watchlist | 0.1000 | 0.0062 | 3 |
| under@mid_2.75 | 209 | promotable | 0.1800 | 0.2629 | 5 |

## Promotion Recommendation

Promotable candidates:
- `under@mid_2.75` at `0.1800`: ROI 0.2629, 5/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.2000`: ROI 0.2561, 5/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.1200`: ROI 0.1840, 5/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.1500`: ROI 0.1820, 5/5 positive folds, baseline-overlap.
- `over@mid_2.75` at `0.0600`: ROI 0.1773, 4/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.1000`: ROI 0.1673, 5/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.0600`: ROI 0.1598, 5/5 positive folds, baseline-overlap.
- `under@mid_2.75` at `0.0800`: ROI 0.1537, 5/5 positive folds, baseline-overlap.
- `over@low_<=2.25` at `0.0600`: ROI 0.1474, 4/5 positive folds, incremental.
- `over@mid_2.75` at `0.0800`: ROI 0.1311, 4/5 positive folds, baseline-overlap.
- `over@low_<=2.25` at `0.1000`: ROI 0.1210, 4/5 positive folds, incremental.
- `over@mid_2.50` at `0.2000`: ROI 0.1091, 4/5 positive folds, incremental.
- `over@mid_2.75` at `0.1000`: ROI 0.1084, 4/5 positive folds, baseline-overlap.
- `under@low_<=2.25` at `0.1200`: ROI 0.0610, 4/5 positive folds, incremental.
- `under@low_<=2.25` at `0.1000`: ROI 0.0550, 4/5 positive folds, incremental.

Watchlist candidates:
- `over@low_<=2.25` at `0.0800`: ROI 0.1118, 3/5 positive folds.
- `over@mid_2.50` at `0.1200`: ROI 0.0774, 4/5 positive folds.
- `over@low_<=2.25` at `0.1200`: ROI 0.0757, 3/5 positive folds.
- `over@mid_2.75` at `0.1200`: ROI 0.0753, 3/5 positive folds.
- `over@mid_2.50` at `0.1000`: ROI 0.0560, 3/5 positive folds.
- `over@mid_2.50` at `0.0600`: ROI 0.0431, 3/5 positive folds.
- `over@mid_2.50` at `0.0800`: ROI 0.0401, 3/5 positive folds.
- `over@mid_2.50` at `0.1500`: ROI 0.0397, 4/5 positive folds.
- `under@high_>=3.00` at `0.1800`: ROI 0.0370, 2/5 positive folds.
- `under@low_<=2.25` at `0.1500`: ROI 0.0258, 2/5 positive folds.

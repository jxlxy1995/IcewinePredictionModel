# Close-Market Baseline Evaluation

- CSV: `local_data\training\baseline_main_leagues_20260530-1422.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Market samples | 15990 |
| Evaluated market samples | 15326 |
| Skipped market samples | 664 |

## Market Metrics

| Market | Evaluated | Skipped | Accuracy | Log loss | Brier | Overround | Flat bet profit | Flat bet ROI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| asian_handicap | 4928 | 402 | 0.5244 | 0.6921 | 0.4412 | 1.0273 | -92.6695 | -0.0188 |
| total_goals | 5068 | 262 | 0.5199 | 0.6924 | 0.4474 | 1.0320 | -111.2930 | -0.0220 |
| match_winner | 5330 | 0 | 0.5032 | 1.0055 | 0.6015 | 1.0390 | -190.4020 | -0.0357 |

## Predicted Side Distribution

### asian_handicap

| Side | Count |
| --- | ---: |
| home | 2527 |
| away | 2401 |

### total_goals

| Side | Count |
| --- | ---: |
| over | 2560 |
| under | 2508 |

### match_winner

| Side | Count |
| --- | ---: |
| home | 3608 |
| away | 1690 |
| draw | 32 |

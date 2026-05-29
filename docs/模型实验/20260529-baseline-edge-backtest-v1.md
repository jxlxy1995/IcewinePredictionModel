# Baseline Edge Backtest v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Thresholds | 0.0000, 0.0200, 0.0400, 0.0600, 0.0800, 0.1000 |

## asian_handicap

| Metric | Value |
| --- | ---: |
| Train rows | 3317 |
| Validation rows | 853 |
| Skipped rows | 1160 |

### raw_hgb_team_form_plus_all_markets

| Metric | Value |
| --- | ---: |
| Estimator | HistGradientBoostingClassifier |
| Calibration | none |
| Features | 32 |
| Accuracy | 0.5487 |
| Log loss | 0.7781 |
| Brier | 0.5166 |

| Threshold | Bets | Accuracy | Profit | ROI |
| ---: | ---: | ---: | ---: | ---: |
| 0.0000 | 853 | 0.5522 | 60.3310 | 0.0707 |
| 0.0200 | 761 | 0.5480 | 47.9340 | 0.0630 |
| 0.0400 | 688 | 0.5422 | 34.8220 | 0.0506 |
| 0.0600 | 611 | 0.5417 | 30.0270 | 0.0491 |
| 0.0800 | 522 | 0.5460 | 29.6310 | 0.0568 |
| 0.1000 | 456 | 0.5395 | 19.8310 | 0.0435 |

### calibrated_hgb_team_form_plus_all_markets

| Metric | Value |
| --- | ---: |
| Estimator | HistGradientBoostingClassifier |
| Calibration | sigmoid |
| Features | 32 |
| Accuracy | 0.5264 |
| Log loss | 0.6960 |
| Brier | 0.4982 |

| Threshold | Bets | Accuracy | Profit | ROI |
| ---: | ---: | ---: | ---: | ---: |
| 0.0000 | 853 | 0.4853 | -27.3720 | -0.0321 |
| 0.0200 | 340 | 0.4971 | 4.4180 | 0.0130 |
| 0.0400 | 81 | 0.5185 | 5.9130 | 0.0730 |
| 0.0600 | 17 | 0.5882 | 4.0900 | 0.2406 |
| 0.0800 | 2 | 0.5000 | 0.0400 | 0.0200 |
| 0.1000 | 0 | - | - | - |

## total_goals

| Metric | Value |
| --- | ---: |
| Train rows | 3476 |
| Validation rows | 891 |
| Skipped rows | 963 |

### raw_hgb_team_form_plus_all_markets

| Metric | Value |
| --- | ---: |
| Estimator | HistGradientBoostingClassifier |
| Calibration | none |
| Features | 32 |
| Accuracy | 0.5354 |
| Log loss | 0.7416 |
| Brier | 0.5399 |

| Threshold | Bets | Accuracy | Profit | ROI |
| ---: | ---: | ---: | ---: | ---: |
| 0.0000 | 891 | 0.5320 | 23.3520 | 0.0262 |
| 0.0200 | 800 | 0.5363 | 27.0330 | 0.0338 |
| 0.0400 | 709 | 0.5303 | 15.6730 | 0.0221 |
| 0.0600 | 638 | 0.5266 | 8.9820 | 0.0141 |
| 0.0800 | 560 | 0.5268 | 7.3820 | 0.0132 |
| 0.1000 | 472 | 0.5212 | 1.1130 | 0.0024 |

### calibrated_hgb_team_form_plus_all_markets

| Metric | Value |
| --- | ---: |
| Estimator | HistGradientBoostingClassifier |
| Calibration | sigmoid |
| Features | 32 |
| Accuracy | 0.4994 |
| Log loss | 0.6936 |
| Brier | 0.5004 |

| Threshold | Bets | Accuracy | Profit | ROI |
| ---: | ---: | ---: | ---: | ---: |
| 0.0000 | 891 | 0.4815 | -39.0830 | -0.0439 |
| 0.0200 | 311 | 0.4823 | -8.2700 | -0.0266 |
| 0.0400 | 37 | 0.5135 | 1.9890 | 0.0538 |
| 0.0600 | 0 | - | - | - |
| 0.0800 | 0 | - | - | - |
| 0.1000 | 0 | - | - | - |


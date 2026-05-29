# Baseline Asian Handicap Model v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Train rows | 3317 |
| Validation rows | 853 |
| Skipped rows | 1160 |

## Close-Market Reference

| Model | Evaluated | Accuracy | Log loss | Brier |
| --- | ---: | ---: | ---: | ---: |
| close_market_asian_handicap | 853 | 0.5287 | 0.6971 | 0.4978 |

## Model Metrics

| Model | Estimator | Features | Accuracy | Log loss | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| team_form_plus_match_winner_market | LogisticRegression | 24 | 0.5064 | 0.6965 | 0.4996 |
| team_form_plus_all_markets | LogisticRegression | 32 | 0.5334 | 0.6993 | 0.4990 |
| team_form_plus_all_markets_plus_asian_handicap_dynamic_core | LogisticRegression | 61 | 0.5346 | 0.6991 | 0.5001 |
| team_form_plus_all_markets_plus_all_dynamic_core | LogisticRegression | 90 | 0.5346 | 0.6991 | 0.5001 |

## Predicted Side Distribution

### close_market_asian_handicap

| Side | Count |
| --- | ---: |
| home_cover | 468 |
| away_cover | 385 |

### team_form_plus_match_winner_market

| Side | Count |
| --- | ---: |
| home_cover | 251 |
| away_cover | 602 |

### team_form_plus_all_markets

| Side | Count |
| --- | ---: |
| home_cover | 282 |
| away_cover | 571 |

### team_form_plus_all_markets_plus_asian_handicap_dynamic_core

| Side | Count |
| --- | ---: |
| home_cover | 299 |
| away_cover | 554 |

### team_form_plus_all_markets_plus_all_dynamic_core

| Side | Count |
| --- | ---: |
| home_cover | 299 |
| away_cover | 554 |

## Calibration Buckets

### close_market_asian_handicap

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 853 | 0.5176 | 0.5287 |

### team_form_plus_match_winner_market

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 853 | 0.5222 | 0.5064 |

### team_form_plus_all_markets

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 847 | 0.5272 | 0.5336 |
| 0.60-0.70 | 6 | 0.6275 | 0.5000 |

### team_form_plus_all_markets_plus_asian_handicap_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 834 | 0.5271 | 0.5384 |
| 0.60-0.70 | 19 | 0.6262 | 0.3684 |

### team_form_plus_all_markets_plus_all_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 834 | 0.5270 | 0.5372 |
| 0.60-0.70 | 19 | 0.6267 | 0.4211 |


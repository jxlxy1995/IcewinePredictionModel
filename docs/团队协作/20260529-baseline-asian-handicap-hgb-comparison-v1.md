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
| hgb_team_form_plus_match_winner_market | HistGradientBoostingClassifier | 24 | 0.5205 | 0.7778 | 0.5288 |
| hgb_team_form_plus_all_markets | HistGradientBoostingClassifier | 32 | 0.5487 | 0.7781 | 0.5166 |
| hgb_team_form_plus_all_markets_plus_asian_handicap_dynamic_core | HistGradientBoostingClassifier | 61 | 0.5475 | 0.7852 | 0.5145 |
| hgb_team_form_plus_all_markets_plus_all_dynamic_core | HistGradientBoostingClassifier | 90 | 0.5416 | 0.7819 | 0.5135 |

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

### hgb_team_form_plus_match_winner_market

| Side | Count |
| --- | ---: |
| home_cover | 391 |
| away_cover | 462 |

### hgb_team_form_plus_all_markets

| Side | Count |
| --- | ---: |
| home_cover | 407 |
| away_cover | 446 |

### hgb_team_form_plus_all_markets_plus_asian_handicap_dynamic_core

| Side | Count |
| --- | ---: |
| home_cover | 418 |
| away_cover | 435 |

### hgb_team_form_plus_all_markets_plus_all_dynamic_core

| Side | Count |
| --- | ---: |
| home_cover | 387 |
| away_cover | 466 |

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

### hgb_team_form_plus_match_winner_market

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 369 | 0.5480 | 0.5041 |
| 0.60-0.70 | 280 | 0.6465 | 0.5214 |
| 0.70-0.80 | 162 | 0.7426 | 0.5247 |
| 0.80-0.90 | 40 | 0.8295 | 0.6250 |
| 0.90-1.00 | 2 | 0.9131 | 1.0000 |

### hgb_team_form_plus_all_markets

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 392 | 0.5487 | 0.5332 |
| 0.60-0.70 | 286 | 0.6469 | 0.5490 |
| 0.70-0.80 | 142 | 0.7370 | 0.5704 |
| 0.80-0.90 | 31 | 0.8331 | 0.6452 |
| 0.90-1.00 | 2 | 0.9110 | 0.5000 |

### hgb_team_form_plus_all_markets_plus_asian_handicap_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 393 | 0.5490 | 0.5293 |
| 0.60-0.70 | 275 | 0.6481 | 0.5564 |
| 0.70-0.80 | 155 | 0.7450 | 0.5548 |
| 0.80-0.90 | 28 | 0.8332 | 0.6429 |
| 0.90-1.00 | 2 | 0.9216 | 1.0000 |

### hgb_team_form_plus_all_markets_plus_all_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 412 | 0.5474 | 0.5121 |
| 0.60-0.70 | 268 | 0.6482 | 0.5485 |
| 0.70-0.80 | 138 | 0.7436 | 0.5870 |
| 0.80-0.90 | 34 | 0.8340 | 0.6765 |
| 0.90-1.00 | 1 | 0.9115 | 0.0000 |


# Baseline Total Goals Model v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Train rows | 3476 |
| Validation rows | 891 |
| Skipped rows | 963 |

## Close-Market Reference

| Model | Evaluated | Accuracy | Log loss | Brier |
| --- | ---: | ---: | ---: | ---: |
| close_market_total_goals | 891 | 0.5174 | 0.6927 | 0.4996 |

## Model Metrics

| Model | Estimator | Features | Accuracy | Log loss | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| team_form_plus_match_winner_market | LogisticRegression | 24 | 0.4871 | 0.6970 | 0.5039 |
| team_form_plus_all_markets | LogisticRegression | 32 | 0.4994 | 0.6991 | 0.5059 |
| team_form_plus_all_markets_plus_total_goals_dynamic_core | LogisticRegression | 61 | 0.4938 | 0.6991 | 0.5059 |
| team_form_plus_all_markets_plus_all_dynamic_core | LogisticRegression | 90 | 0.4938 | 0.6993 | 0.5061 |
| hgb_team_form_plus_match_winner_market | HistGradientBoostingClassifier | 24 | 0.5039 | 0.7410 | 0.5409 |
| hgb_team_form_plus_all_markets | HistGradientBoostingClassifier | 32 | 0.5354 | 0.7416 | 0.5399 |
| hgb_team_form_plus_all_markets_plus_total_goals_dynamic_core | HistGradientBoostingClassifier | 61 | 0.5163 | 0.7503 | 0.5463 |
| hgb_team_form_plus_all_markets_plus_all_dynamic_core | HistGradientBoostingClassifier | 90 | 0.5230 | 0.7466 | 0.5437 |

## Predicted Side Distribution

### close_market_total_goals

| Side | Count |
| --- | ---: |
| over | 461 |
| under | 430 |

### team_form_plus_match_winner_market

| Side | Count |
| --- | ---: |
| over | 300 |
| under | 591 |

### team_form_plus_all_markets

| Side | Count |
| --- | ---: |
| over | 311 |
| under | 580 |

### team_form_plus_all_markets_plus_total_goals_dynamic_core

| Side | Count |
| --- | ---: |
| over | 316 |
| under | 575 |

### team_form_plus_all_markets_plus_all_dynamic_core

| Side | Count |
| --- | ---: |
| over | 320 |
| under | 571 |

### hgb_team_form_plus_match_winner_market

| Side | Count |
| --- | ---: |
| over | 425 |
| under | 466 |

### hgb_team_form_plus_all_markets

| Side | Count |
| --- | ---: |
| over | 423 |
| under | 468 |

### hgb_team_form_plus_all_markets_plus_total_goals_dynamic_core

| Side | Count |
| --- | ---: |
| over | 420 |
| under | 471 |

### hgb_team_form_plus_all_markets_plus_all_dynamic_core

| Side | Count |
| --- | ---: |
| over | 428 |
| under | 463 |

## Calibration Buckets

### close_market_total_goals

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 891 | 0.5148 | 0.5174 |

### team_form_plus_match_winner_market

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 867 | 0.5339 | 0.4856 |
| 0.60-0.70 | 23 | 0.6235 | 0.5217 |
| 0.70-0.80 | 1 | 0.7103 | 1.0000 |

### team_form_plus_all_markets

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 833 | 0.5375 | 0.4994 |
| 0.60-0.70 | 56 | 0.6216 | 0.4821 |
| 0.70-0.80 | 2 | 0.7308 | 1.0000 |

### team_form_plus_all_markets_plus_total_goals_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 833 | 0.5373 | 0.4934 |
| 0.60-0.70 | 56 | 0.6230 | 0.4821 |
| 0.70-0.80 | 2 | 0.7293 | 1.0000 |

### team_form_plus_all_markets_plus_all_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 830 | 0.5371 | 0.4952 |
| 0.60-0.70 | 59 | 0.6222 | 0.4576 |
| 0.70-0.80 | 2 | 0.7298 | 1.0000 |

### hgb_team_form_plus_match_winner_market

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 401 | 0.5493 | 0.4988 |
| 0.60-0.70 | 295 | 0.6460 | 0.4814 |
| 0.70-0.80 | 159 | 0.7399 | 0.5723 |
| 0.80-0.90 | 35 | 0.8296 | 0.4571 |
| 0.90-1.00 | 1 | 0.9126 | 0.0000 |

### hgb_team_form_plus_all_markets

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 403 | 0.5475 | 0.5484 |
| 0.60-0.70 | 266 | 0.6443 | 0.5639 |
| 0.70-0.80 | 170 | 0.7410 | 0.4706 |
| 0.80-0.90 | 49 | 0.8363 | 0.5102 |
| 0.90-1.00 | 3 | 0.9099 | 0.3333 |

### hgb_team_form_plus_all_markets_plus_total_goals_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 391 | 0.5496 | 0.4962 |
| 0.60-0.70 | 261 | 0.6432 | 0.5900 |
| 0.70-0.80 | 165 | 0.7462 | 0.4667 |
| 0.80-0.90 | 72 | 0.8368 | 0.4722 |
| 0.90-1.00 | 2 | 0.9267 | 0.5000 |

### hgb_team_form_plus_all_markets_plus_all_dynamic_core

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.50-0.60 | 407 | 0.5480 | 0.5283 |
| 0.60-0.70 | 251 | 0.6457 | 0.5657 |
| 0.70-0.80 | 169 | 0.7434 | 0.4320 |
| 0.80-0.90 | 63 | 0.8353 | 0.5556 |
| 0.90-1.00 | 1 | 0.9084 | 1.0000 |


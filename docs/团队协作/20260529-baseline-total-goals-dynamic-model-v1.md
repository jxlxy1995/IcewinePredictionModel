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


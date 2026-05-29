# Baseline Match Winner Model v1

- Feature CSV: `local_data\training\baseline_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Train rows | 4262 |
| Validation rows | 1068 |

## Close-Market Reference

| Model | Evaluated | Accuracy | Log loss | Brier |
| --- | ---: | ---: | ---: | ---: |
| close_market_match_winner | 1068 | 0.5009 | 1.3146 | 0.6071 |

## Model Metrics

| Model | Estimator | Features | Accuracy | Log loss | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| team_form_only | LogisticRegression | 20 | 0.3811 | 1.1378 | 0.6582 |
| team_form_plus_market | LogisticRegression | 24 | 0.4579 | 1.3126 | 0.6275 |

## Predicted Result Distribution

### close_market_match_winner

| Result | Count |
| --- | ---: |
| home_win | 737 |
| draw | 2 |
| away_win | 329 |

### team_form_only

| Result | Count |
| --- | ---: |
| home_win | 347 |
| draw | 276 |
| away_win | 445 |

### team_form_plus_market

| Result | Count |
| --- | ---: |
| home_win | 437 |
| draw | 255 |
| away_win | 376 |

## Calibration Buckets

### close_market_match_winner

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.30-0.40 | 187 | 0.3760 | 0.3957 |
| 0.40-0.50 | 409 | 0.4471 | 0.4377 |
| 0.50-0.60 | 251 | 0.5463 | 0.5538 |
| 0.60-0.70 | 146 | 0.6422 | 0.5959 |
| 0.70-0.80 | 62 | 0.7435 | 0.7097 |
| 0.80-0.90 | 13 | 0.8306 | 0.9231 |

### team_form_only

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.30-0.40 | 798 | 0.3679 | 0.3283 |
| 0.40-0.50 | 256 | 0.4314 | 0.5195 |
| 0.50-0.60 | 14 | 0.5236 | 0.8571 |

### team_form_plus_market

| Bucket | Samples | Avg confidence | Accuracy |
| --- | ---: | ---: | ---: |
| 0.30-0.40 | 339 | 0.3747 | 0.3658 |
| 0.40-0.50 | 405 | 0.4406 | 0.4123 |
| 0.50-0.60 | 194 | 0.5427 | 0.5412 |
| 0.60-0.70 | 97 | 0.6449 | 0.6907 |
| 0.70-0.80 | 31 | 0.7312 | 0.7742 |
| 0.80-0.90 | 2 | 0.8021 | 1.0000 |


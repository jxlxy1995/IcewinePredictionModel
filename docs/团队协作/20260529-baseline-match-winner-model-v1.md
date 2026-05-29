# Baseline Match Winner Model v1

- Feature CSV: `local_data\training\baseline_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Train rows | 4262 |
| Validation rows | 1068 |

## Close-Market Reference

| Model | Accuracy | Log loss | Brier |
| --- | ---: | ---: | ---: |
| close_market_match_winner | 0.5032 | 1.0055 | 0.6015 |

## Model Metrics

| Model | Estimator | Features | Accuracy | Log loss | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| team_form_only | LogisticRegression | 20 | 0.3811 | 1.1378 | 0.6582 |
| team_form_plus_market | LogisticRegression | 24 | 0.4579 | 1.3126 | 0.6275 |

## Predicted Result Distribution

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


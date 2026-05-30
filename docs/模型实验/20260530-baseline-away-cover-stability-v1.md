# Baseline Away Cover Stability v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260530.csv`
- Scope: `asian_handicap raw_hgb_team_form_plus_all_markets away_cover`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Folds | 5 |
| Train ratio | 0.6000 |
| Validation ratio | 0.1000 |
| Thresholds | 0.0800, 0.1000, 0.1200, 0.1500, 0.2000 |

## Threshold Stability

| Threshold | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0800 | 689 | 4 | 41.7770 | 0.0606 | -0.0322 |
| 0.1000 | 610 | 5 | 52.3050 | 0.0857 | 0.0061 |
| 0.1200 | 535 | 4 | 51.8910 | 0.0970 | -0.0143 |
| 0.1500 | 436 | 3 | 35.7650 | 0.0820 | -0.1167 |
| 0.2000 | 293 | 2 | 19.4670 | 0.0664 | -0.1051 |

## League Stability

| League | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Major League Soccer (USA) | 35 | 2 | -0.0990 | -0.0028 | -0.4463 |
| Super League (China) | 33 | 4 | 9.5050 | 0.2880 | -0.3757 |
| J1 League (Japan) | 31 | 3 | 6.1260 | 0.1976 | -0.0467 |
| Liga Profesional Argentina (Argentina) | 24 | 3 | 8.8230 | 0.3676 | -1.0000 |
| Jupiler Pro League (Belgium) | 22 | 3 | 10.3010 | 0.4682 | -0.0560 |
| League One (England) | 22 | 3 | 5.2570 | 0.2390 | -1.0000 |
| Championship (England) | 21 | 3 | 0.4040 | 0.0192 | -0.1350 |
| Pro League (Saudi-Arabia) | 21 | 1 | 2.0040 | 0.0954 | -0.3367 |
| 1. Division (Norway) | 20 | 1 | -6.4590 | -0.3230 | -1.0000 |
| K League 1 (South-Korea) | 19 | 4 | 6.4930 | 0.3417 | -0.0800 |
| 1. Division (Denmark) | 18 | 3 | 5.0600 | 0.2811 | -1.0000 |
| Premier Division (Ireland) | 18 | 1 | -0.9490 | -0.0527 | -1.0000 |
| Premier League | 18 | 0 | -8.1890 | -0.4549 | -1.0000 |
| Allsvenskan (Sweden) | 17 | 3 | 0.1050 | 0.0062 | -1.0000 |
| Eredivisie (Netherlands) | 17 | 2 | 0.2160 | 0.0127 | -1.0000 |
| Super League 1 (Greece) | 17 | 3 | 2.2330 | 0.1314 | -0.2886 |
| Bundesliga (Austria) | 15 | 2 | -5.2720 | -0.3515 | -1.0000 |
| Superettan (Sweden) | 15 | 2 | 2.7010 | 0.1801 | -1.0000 |
| La Liga | 14 | 1 | -5.9100 | -0.4221 | -0.7029 |
| Segunda División (Spain) | 14 | 5 | 3.8720 | 0.2766 | 0.0075 |
| Liga 1 (Indonesia) | 13 | 1 | -5.2780 | -0.4060 | -1.0000 |
| Serie B (Italy) | 13 | 1 | -1.2260 | -0.0943 | -0.3667 |
| Bundesliga (Germany) | 12 | 2 | -1.9980 | -0.1665 | -1.0000 |
| Serie A | 12 | 3 | 0.1070 | 0.0089 | -1.0000 |
| Süper Lig (Turkey) | 12 | 1 | -4.2390 | -0.3533 | -1.0000 |
| Eerste Divisie (Netherlands) | 11 | 1 | -3.5560 | -0.3233 | -0.5374 |
| 2. Bundesliga (Germany) | 10 | 2 | 3.4840 | 0.3484 | -1.0000 |
| Ekstraklasa (Poland) | 10 | 3 | 1.9030 | 0.1903 | -1.0000 |
| K League 2 (South-Korea) | 9 | 3 | 2.6710 | 0.2968 | -1.0000 |
| Super League (Switzerland) | 9 | 2 | 2.6970 | 0.2997 | -1.0000 |
| Liga I (Romania) | 8 | 2 | 5.5970 | 0.6996 | 0.6118 |
| Ligue 1 (France) | 8 | 3 | 5.9750 | 0.7469 | 0.3330 |
| Ligue 2 (France) | 8 | 2 | -2.0130 | -0.2516 | -0.6246 |
| Premiership (Scotland) | 8 | 2 | -0.1610 | -0.0201 | -0.3417 |
| Primeira Liga (Portugal) | 8 | 2 | -0.3040 | -0.0380 | -1.0000 |
| Premier League (Russia) | 7 | 1 | -1.4140 | -0.2020 | -1.0000 |
| Primera División (Chile) | 7 | 2 | 0.6150 | 0.0879 | -1.0000 |
| Veikkausliiga (Finland) | 7 | 2 | 1.0010 | 0.1430 | -1.0000 |
| Ykkösliiga (Finland) | 7 | 3 | 4.7990 | 0.6856 | -0.0540 |
| Superliga (Denmark) | 6 | 1 | -0.3410 | -0.0568 | -1.0000 |
| Eliteserien (Norway) | 5 | 2 | -1.1280 | -0.2256 | -1.0000 |
| Serie A (Brazil) | 5 | 3 | 4.8880 | 0.9776 | 0.8130 |

## Line Bucket Stability

| Line bucket | Bets | Positive ROI folds | Profit | ROI | Worst fold ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| away_favorite | 346 | 2 | 17.4120 | 0.0503 | -0.1635 |
| away_underdog | 181 | 4 | 20.6910 | 0.1143 | -0.1212 |
| pickem | 83 | 3 | 14.2020 | 0.1711 | -0.1070 |

# Baseline Market Diagnostics v1

- Feature CSV: `local_data\training\baseline_features_main_leagues_20260529.csv`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Validation rows | 1068 |

## Asian Handicap

| Metric | Value |
| --- | ---: |
| Eligible rows | 853 |
| Skipped rows | 215 |
| Accuracy | 0.5287 |

### Side Distribution

| Side | Actual | Predicted |
| --- | ---: | ---: |
| away_cover | 427 | 385 |
| home_cover | 426 | 468 |

### By League

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| Major League Soccer (USA) | 55 | 0.4182 | away_cover:28, home_cover:27 | away_cover:26, home_cover:29 |
| J1 League (Japan) | 37 | 0.5135 | away_cover:18, home_cover:19 | away_cover:14, home_cover:23 |
| La Liga | 35 | 0.5143 | away_cover:14, home_cover:21 | away_cover:17, home_cover:18 |
| Serie A (Brazil) | 33 | 0.6061 | away_cover:18, home_cover:15 | away_cover:13, home_cover:20 |
| Super League (China) | 33 | 0.4545 | away_cover:22, home_cover:11 | away_cover:10, home_cover:23 |
| Premier League | 30 | 0.5667 | away_cover:12, home_cover:18 | away_cover:15, home_cover:15 |
| Superettan (Sweden) | 29 | 0.5862 | away_cover:13, home_cover:16 | away_cover:9, home_cover:20 |
| Pro League (Saudi-Arabia) | 28 | 0.4286 | away_cover:12, home_cover:16 | away_cover:18, home_cover:10 |
| Serie A | 27 | 0.5556 | away_cover:17, home_cover:10 | away_cover:11, home_cover:16 |
| 1. Division (Norway) | 23 | 0.6957 | away_cover:10, home_cover:13 | away_cover:11, home_cover:12 |
| Liga 1 (Indonesia) | 23 | 0.4783 | away_cover:10, home_cover:13 | away_cover:14, home_cover:9 |
| Ligue 1 (France) | 23 | 0.5217 | away_cover:15, home_cover:8 | away_cover:12, home_cover:11 |
| Allsvenskan (Sweden) | 22 | 0.6364 | away_cover:11, home_cover:11 | away_cover:13, home_cover:9 |
| Jupiler Pro League (Belgium) | 22 | 0.4091 | away_cover:9, home_cover:13 | away_cover:16, home_cover:6 |
| K League 2 (South-Korea) | 22 | 0.6818 | away_cover:9, home_cover:13 | away_cover:6, home_cover:16 |
| Liga Profesional Argentina (Argentina) | 22 | 0.6818 | away_cover:13, home_cover:9 | away_cover:12, home_cover:10 |
| Super League 1 (Greece) | 22 | 0.5000 | away_cover:11, home_cover:11 | away_cover:12, home_cover:10 |
| Eliteserien (Norway) | 20 | 0.5000 | away_cover:6, home_cover:14 | away_cover:8, home_cover:12 |
| Eredivisie (Netherlands) | 20 | 0.6000 | away_cover:10, home_cover:10 | away_cover:10, home_cover:10 |
| K League 1 (South-Korea) | 20 | 0.5000 | away_cover:10, home_cover:10 | away_cover:10, home_cover:10 |
| Segunda División (Spain) | 20 | 0.5500 | away_cover:12, home_cover:8 | away_cover:7, home_cover:13 |
| Super League (Switzerland) | 20 | 0.6000 | away_cover:11, home_cover:9 | away_cover:9, home_cover:11 |
| Bundesliga (Germany) | 19 | 0.5789 | away_cover:10, home_cover:9 | away_cover:12, home_cover:7 |
| 2. Bundesliga (Germany) | 18 | 0.5556 | away_cover:7, home_cover:11 | away_cover:9, home_cover:9 |
| Ekstraklasa (Poland) | 18 | 0.4444 | away_cover:11, home_cover:7 | away_cover:3, home_cover:15 |
| Premiership (Scotland) | 18 | 0.5556 | away_cover:8, home_cover:10 | away_cover:6, home_cover:12 |
| Primeira Liga (Portugal) | 18 | 0.5556 | away_cover:9, home_cover:9 | away_cover:11, home_cover:7 |
| Süper Lig (Turkey) | 17 | 0.4706 | away_cover:8, home_cover:9 | away_cover:5, home_cover:12 |
| Veikkausliiga (Finland) | 17 | 0.5294 | away_cover:7, home_cover:10 | away_cover:3, home_cover:14 |
| 1. Division (Denmark) | 16 | 0.5625 | away_cover:12, home_cover:4 | away_cover:7, home_cover:9 |
| Premier Division (Ireland) | 16 | 0.6250 | away_cover:9, home_cover:7 | away_cover:7, home_cover:9 |
| Bundesliga (Austria) | 15 | 0.4667 | away_cover:8, home_cover:7 | away_cover:6, home_cover:9 |
| Premier League (Russia) | 15 | 0.6000 | away_cover:6, home_cover:9 | away_cover:8, home_cover:7 |
| Superliga (Denmark) | 15 | 0.4667 | away_cover:10, home_cover:5 | away_cover:4, home_cover:11 |
| Primera División (Chile) | 14 | 0.2143 | away_cover:6, home_cover:8 | away_cover:7, home_cover:7 |
| Serie B (Italy) | 14 | 0.3571 | away_cover:6, home_cover:8 | away_cover:5, home_cover:9 |
| Liga I (Romania) | 13 | 0.6154 | away_cover:8, home_cover:5 | away_cover:9, home_cover:4 |

### By Line

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| -0.25 | 144 | 0.5139 | away_cover:63, home_cover:81 | away_cover:81, home_cover:63 |
| -0.50 | 144 | 0.5833 | away_cover:61, home_cover:83 | away_cover:73, home_cover:71 |
| 0.00 | 108 | 0.5556 | away_cover:50, home_cover:58 | away_cover:46, home_cover:62 |
| -0.75 | 90 | 0.4667 | away_cover:62, home_cover:28 | away_cover:44, home_cover:46 |
| 0.50 | 77 | 0.5065 | away_cover:40, home_cover:37 | away_cover:22, home_cover:55 |
| 0.25 | 75 | 0.6000 | away_cover:39, home_cover:36 | away_cover:17, home_cover:58 |
| -1.00 | 58 | 0.5862 | away_cover:26, home_cover:32 | away_cover:26, home_cover:32 |
| -1.25 | 45 | 0.5333 | away_cover:31, home_cover:14 | away_cover:24, home_cover:21 |
| -1.50 | 23 | 0.3913 | away_cover:11, home_cover:12 | away_cover:11, home_cover:12 |
| 0.75 | 23 | 0.5652 | away_cover:9, home_cover:14 | away_cover:11, home_cover:12 |
| -1.75 | 16 | 0.4375 | away_cover:12, home_cover:4 | away_cover:11, home_cover:5 |
| 1.00 | 15 | 0.1333 | away_cover:8, home_cover:7 | away_cover:5, home_cover:10 |
| -2.00 | 11 | 0.3636 | away_cover:5, home_cover:6 | away_cover:6, home_cover:5 |

### By Market Confidence

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| 0.50-0.60 | 853 | 0.5287 | away_cover:427, home_cover:426 | away_cover:385, home_cover:468 |

### By Actual Side

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| away_cover | 427 | 0.4801 | away_cover:427 | away_cover:205, home_cover:222 |
| home_cover | 426 | 0.5775 | home_cover:426 | away_cover:180, home_cover:246 |

## Total Goals

| Metric | Value |
| --- | ---: |
| Eligible rows | 891 |
| Skipped rows | 177 |
| Accuracy | 0.5174 |

### Side Distribution

| Side | Actual | Predicted |
| --- | ---: | ---: |
| over | 449 | 461 |
| under | 442 | 430 |

### By League

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| Major League Soccer (USA) | 60 | 0.5833 | over:33, under:27 | over:40, under:20 |
| La Liga | 39 | 0.5128 | over:17, under:22 | over:20, under:19 |
| J1 League (Japan) | 37 | 0.4865 | over:18, under:19 | over:15, under:22 |
| Serie A | 35 | 0.4571 | over:17, under:18 | over:16, under:19 |
| Superettan (Sweden) | 34 | 0.7059 | over:20, under:14 | over:20, under:14 |
| Serie A (Brazil) | 32 | 0.6250 | over:20, under:12 | over:18, under:14 |
| Pro League (Saudi-Arabia) | 31 | 0.6129 | over:16, under:15 | over:14, under:17 |
| Super League (China) | 31 | 0.3871 | over:16, under:15 | over:17, under:14 |
| K League 2 (South-Korea) | 28 | 0.4643 | over:15, under:13 | over:14, under:14 |
| Premier League | 28 | 0.5714 | over:11, under:17 | over:13, under:15 |
| 1. Division (Norway) | 24 | 0.5417 | over:12, under:12 | over:11, under:13 |
| Super League 1 (Greece) | 24 | 0.4583 | over:16, under:8 | over:15, under:9 |
| Ekstraklasa (Poland) | 23 | 0.5217 | over:11, under:12 | over:12, under:11 |
| Jupiler Pro League (Belgium) | 22 | 0.6818 | over:11, under:11 | over:16, under:6 |
| Liga 1 (Indonesia) | 22 | 0.5000 | over:10, under:12 | over:11, under:11 |
| Allsvenskan (Sweden) | 21 | 0.5238 | over:11, under:10 | over:15, under:6 |
| Ligue 1 (France) | 21 | 0.4286 | over:9, under:12 | over:11, under:10 |
| Primeira Liga (Portugal) | 21 | 0.4286 | over:7, under:14 | over:7, under:14 |
| 2. Bundesliga (Germany) | 20 | 0.4500 | over:8, under:12 | over:11, under:9 |
| Bundesliga (Germany) | 20 | 0.6500 | over:11, under:9 | over:12, under:8 |
| Segunda División (Spain) | 20 | 0.6500 | over:11, under:9 | over:10, under:10 |
| Eliteserien (Norway) | 19 | 0.5789 | over:9, under:10 | over:5, under:14 |
| Eredivisie (Netherlands) | 18 | 0.6667 | over:9, under:9 | over:9, under:9 |
| K League 1 (South-Korea) | 18 | 0.5000 | over:9, under:9 | over:10, under:8 |
| Liga I (Romania) | 18 | 0.4444 | over:9, under:9 | over:9, under:9 |
| Premier Division (Ireland) | 18 | 0.5000 | over:11, under:7 | over:8, under:10 |
| Premiership (Scotland) | 18 | 0.4444 | over:10, under:8 | over:10, under:8 |
| Super League (Switzerland) | 18 | 0.5556 | over:8, under:10 | over:10, under:8 |
| Superliga (Denmark) | 18 | 0.3333 | over:11, under:7 | over:9, under:9 |
| Veikkausliiga (Finland) | 18 | 0.5000 | over:6, under:12 | over:11, under:7 |
| 1. Division (Denmark) | 17 | 0.3529 | over:10, under:7 | over:7, under:10 |
| Premier League (Russia) | 17 | 0.4706 | over:8, under:9 | over:5, under:12 |
| Serie B (Italy) | 17 | 0.3529 | over:9, under:8 | over:8, under:9 |
| Bundesliga (Austria) | 16 | 0.5000 | over:9, under:7 | over:7, under:9 |
| Süper Lig (Turkey) | 15 | 0.5333 | over:7, under:8 | over:8, under:7 |
| Liga Profesional Argentina (Argentina) | 13 | 0.3846 | over:6, under:7 | over:6, under:7 |
| Primera División (Chile) | 13 | 0.6154 | over:9, under:4 | over:4, under:9 |

### By Line

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| 2.50 | 249 | 0.5060 | over:132, under:117 | over:125, under:124 |
| 2.75 | 160 | 0.5188 | over:65, under:95 | over:92, under:68 |
| 3.00 | 128 | 0.5469 | over:64, under:64 | over:68, under:60 |
| 2.25 | 113 | 0.5221 | over:69, under:44 | over:61, under:52 |
| 3.25 | 98 | 0.4796 | over:55, under:43 | over:34, under:64 |
| 3.50 | 66 | 0.6061 | over:31, under:35 | over:31, under:35 |
| 2.00 | 37 | 0.4595 | over:17, under:20 | over:23, under:14 |
| 3.75 | 19 | 0.5263 | over:12, under:7 | over:11, under:8 |

### By Market Confidence

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| 0.50-0.60 | 891 | 0.5174 | over:449, under:442 | over:461, under:430 |

### By Actual Side

| Segment | Rows | Accuracy | Actual counts | Predicted counts |
| --- | ---: | ---: | --- | --- |
| over | 449 | 0.5345 | over:449 | over:240, under:209 |
| under | 442 | 0.5000 | under:442 | over:221, under:221 |


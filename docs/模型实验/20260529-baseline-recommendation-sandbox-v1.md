# Baseline Recommendation Sandbox v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260529.csv`
- Scope: `asian_handicap raw_hgb_team_form_plus_all_markets`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Train rows | 3317 |
| Validation rows | 853 |
| Skipped rows | 1160 |
| Edge threshold | 0.1000 |
| Candidates | 456 |
| Profit | 19.8310 |
| ROI | 0.0435 |
| Displayed candidates | 80 |

## Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| away_cover | 245 | 136 | 17.8500 | 0.0729 |
| home_cover | 211 | 110 | 1.9810 | 0.0094 |

## League Summary

| League | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| Major League Soccer (USA) | 28 | 16 | 3.3210 | 0.1186 |
| Super League (China) | 20 | 12 | 2.9710 | 0.1486 |
| J1 League (Japan) | 18 | 6 | -6.2940 | -0.3497 |
| Superettan (Sweden) | 17 | 11 | 4.3390 | 0.2552 |
| 1. Division (Norway) | 16 | 12 | 6.6130 | 0.4133 |
| La Liga | 16 | 11 | 5.8380 | 0.3649 |
| Liga Profesional Argentina (Argentina) | 16 | 9 | 1.0640 | 0.0665 |
| Serie A | 16 | 4 | -7.9560 | -0.4973 |
| Premier League | 15 | 7 | -1.1030 | -0.0735 |
| Allsvenskan (Sweden) | 14 | 7 | -0.7850 | -0.0561 |
| Liga 1 (Indonesia) | 14 | 7 | -0.5490 | -0.0392 |
| 1. Division (Denmark) | 13 | 8 | 2.4460 | 0.1882 |
| Ligue 1 (France) | 13 | 7 | 0.8760 | 0.0674 |
| Serie A (Brazil) | 13 | 7 | 0.4320 | 0.0332 |
| Jupiler Pro League (Belgium) | 12 | 4 | -4.2980 | -0.3582 |
| Pro League (Saudi-Arabia) | 12 | 7 | 1.3860 | 0.1155 |
| Super League 1 (Greece) | 12 | 7 | 1.5540 | 0.1295 |
| Eliteserien (Norway) | 11 | 5 | -1.1460 | -0.1042 |
| Segunda División (Spain) | 11 | 9 | 5.9980 | 0.5453 |
| Eredivisie (Netherlands) | 10 | 6 | 1.6570 | 0.1657 |
| K League 1 (South-Korea) | 10 | 5 | -0.2290 | -0.0229 |
| Super League (Switzerland) | 10 | 5 | -0.5270 | -0.0527 |
| 2. Bundesliga (Germany) | 9 | 6 | 2.6070 | 0.2897 |
| Bundesliga (Austria) | 9 | 5 | 0.9640 | 0.1071 |
| Ekstraklasa (Poland) | 9 | 5 | 0.7780 | 0.0864 |
| K League 2 (South-Korea) | 9 | 5 | 0.6090 | 0.0677 |
| Liga I (Romania) | 9 | 5 | 0.2960 | 0.0329 |
| Premier Division (Ireland) | 9 | 5 | 0.5270 | 0.0586 |
| Primeira Liga (Portugal) | 9 | 6 | 2.4600 | 0.2733 |
| Veikkausliiga (Finland) | 9 | 5 | 0.9000 | 0.1000 |
| Bundesliga (Germany) | 8 | 5 | 1.7710 | 0.2214 |
| Premier League (Russia) | 8 | 4 | -0.1770 | -0.0221 |
| Premiership (Scotland) | 8 | 3 | -2.3320 | -0.2915 |
| Serie B (Italy) | 8 | 3 | -1.9130 | -0.2391 |
| Primera División (Chile) | 7 | 3 | -0.8990 | -0.1284 |
| Superliga (Denmark) | 7 | 4 | 0.4440 | 0.0634 |
| Süper Lig (Turkey) | 7 | 4 | 0.7950 | 0.1136 |
| Ligue 2 (France) | 6 | 3 | -0.4010 | -0.0668 |
| Ykkösliiga (Finland) | 4 | 3 | 1.7940 | 0.4485 |
| League One (England) | 2 | 0 | -2.0000 | -1.0000 |
| A-League (Australia) | 1 | 0 | -1.0000 | -1.0000 |
| Championship (England) | 1 | 0 | -1.0000 | -1.0000 |

## Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 1493 | 2026-05-05T03:00:00 | La Liga | Sevilla vs Real Sociedad | -0.25 | home_cover | 2.080 | 0.9202 | 0.4713 | 0.4489 | home_cover | 1.0800 |
| 13158 | 2026-05-05T02:00:00 | Pro League (Saudi-Arabia) | Al-Ittihad FC vs Al Kholood | -0.75 | away_cover | 1.862 | 0.8974 | 0.5166 | 0.3808 | away_cover | 0.8620 |
| 13178 | 2026-05-17T02:00:00 | Pro League (Saudi-Arabia) | Al-Ahli Jeddah vs Al Kholood | -1.75 | away_cover | 1.819 | 0.9017 | 0.5273 | 0.3744 | home_cover | -1.0000 |
| 1152 | 2026-05-20T02:30:00 | Premier League | Bournemouth vs Manchester City | 0.75 | home_cover | 2.100 | 0.8347 | 0.4670 | 0.3677 | home_cover | 1.1000 |
| 8349 | 2026-05-19T01:30:00 | Liga I (Romania) | Petrolul Ploiesti vs Oţelul | -0.75 | away_cover | 1.806 | 0.8995 | 0.5329 | 0.3666 | away_cover | 0.8060 |
| 7609 | 2026-05-18T00:30:00 | Super League 1 (Greece) | Panathinaikos vs PAOK | 0.50 | away_cover | 1.884 | 0.8744 | 0.5112 | 0.3632 | home_cover | -1.0000 |
| 1151 | 2026-05-19T03:00:00 | Premier League | Arsenal vs Burnley | -2.50 | away_cover | 1.990 | 0.8511 | 0.4907 | 0.3604 | away_cover | 0.9900 |
| 7585 | 2026-05-03T22:00:00 | Super League 1 (Greece) | Levadiakos vs Volos NFC | -1.00 | home_cover | 2.070 | 0.8297 | 0.4696 | 0.3601 | home_cover | 1.0700 |
| 7610 | 2026-05-21T23:00:00 | Super League 1 (Greece) | Atromitos vs Panserraikos | -1.75 | away_cover | 1.840 | 0.8731 | 0.5159 | 0.3572 | home_cover | -1.0000 |
| 17029 | 2026-05-14T08:30:00 | Major League Soccer (USA) | Minnesota United FC vs Colorado Rapids | -0.75 | away_cover | 2.050 | 0.8282 | 0.4759 | 0.3523 | away_cover | 1.0500 |
| 17027 | 2026-05-14T08:30:00 | Major League Soccer (USA) | FC Dallas vs Vancouver Whitecaps | 0.50 | away_cover | 1.961 | 0.8414 | 0.4977 | 0.3437 | away_cover | 0.9610 |
| 8024 | 2026-05-13T02:30:00 | Super League (Switzerland) | FC Luzern vs FC Zurich | -1.50 | away_cover | 1.854 | 0.8645 | 0.5263 | 0.3382 | away_cover | 0.8540 |
| 14923 | 2026-05-20T20:00:00 | Super League (China) | Hangzhou Greentown vs Shandong Luneng | 0.00 | away_cover | 1.869 | 0.8565 | 0.5194 | 0.3371 | home_cover | -1.0000 |
| 15674 | 2026-05-04T03:00:00 | Liga Profesional Argentina (Argentina) | Racing Club vs Huracan | -0.50 | away_cover | 1.900 | 0.8418 | 0.5067 | 0.3351 | away_cover | 0.9000 |
| 1828 | 2026-05-16T21:30:00 | Bundesliga (Germany) | 1. FC Heidenheim vs FSV Mainz 05 | -0.50 | home_cover | 2.050 | 0.8130 | 0.4789 | 0.3341 | away_cover | -1.0000 |
| 2185 | 2026-05-10T00:00:00 | Serie A | Lazio vs Inter | 0.50 | home_cover | 2.080 | 0.7922 | 0.4713 | 0.3209 | away_cover | -1.0000 |
| 2205 | 2026-05-25T02:45:00 | Serie A | Torino vs Juventus | 1.00 | home_cover | 2.040 | 0.7993 | 0.4801 | 0.3192 | home_cover | 1.0400 |
| 8583 | 2026-05-10T20:00:00 | Premier League (Russia) | Zenit vs FC Sochi | -2.00 | home_cover | 1.877 | 0.8356 | 0.5170 | 0.3186 | away_cover | -1.0000 |
| 16341 | 2026-05-17T13:00:00 | J1 League (Japan) | JEF United Chiba vs Kashima | 0.75 | home_cover | 2.110 | 0.7789 | 0.4621 | 0.3168 | away_cover | -1.0000 |
| 6097 | 2026-05-03T18:15:00 | Eredivisie (Netherlands) | FC Volendam vs Heerenveen | 0.25 | away_cover | 1.961 | 0.8124 | 0.4977 | 0.3147 | away_cover | 0.9610 |
| 16312 | 2026-05-03T14:00:00 | J1 League (Japan) | Cerezo Osaka vs Avispa Fukuoka | -0.75 | away_cover | 1.840 | 0.8446 | 0.5306 | 0.3140 | away_cover | 0.8400 |
| 18380 | 2026-05-05T16:30:00 | Liga 1 (Indonesia) | Persepam Madura Utd vs Bali United | -0.25 | away_cover | 1.813 | 0.8446 | 0.5307 | 0.3139 | home_cover | -1.0000 |
| 16323 | 2026-05-06T16:00:00 | J1 League (Japan) | Kawasaki Frontale vs Tokyo Verdy | -0.25 | home_cover | 1.847 | 0.8413 | 0.5285 | 0.3128 | home_cover | 0.8470 |
| 14029 | 2026-05-10T23:00:00 | Eliteserien (Norway) | Tromso vs Molde | -0.50 | home_cover | 1.970 | 0.8096 | 0.4977 | 0.3119 | home_cover | 0.9700 |
| 5799 | 2026-05-12T03:15:00 | Primeira Liga (Portugal) | Rio Ave vs Sporting CP | 2.00 | home_cover | 2.060 | 0.7804 | 0.4699 | 0.3105 | away_cover | -1.0000 |
| 8598 | 2026-05-20T22:30:00 | Premier League (Russia) | Ural vs Dinamo Makhachkala | -0.25 | home_cover | 2.170 | 0.7569 | 0.4474 | 0.3095 | away_cover | -1.0000 |
| 14673 | 2026-05-18T00:30:00 | Primera División (Chile) | Huachipato vs Union La Calera | -0.25 | home_cover | 2.100 | 0.7709 | 0.4633 | 0.3076 | home_cover | 1.1000 |
| 17576 | 2026-05-28T00:00:00 | Ykkösliiga (Finland) | Klubi-04 vs PK-35 | 0.50 | away_cover | 1.854 | 0.8224 | 0.5190 | 0.3034 | away_cover | 0.8540 |
| 4338 | 2026-05-17T21:30:00 | 2. Bundesliga (Germany) | 1. FC Magdeburg vs 1. FC Kaiserslautern | -1.25 | away_cover | 1.854 | 0.8219 | 0.5239 | 0.2980 | away_cover | 0.8540 |
| 13156 | 2026-05-05T00:10:00 | Pro League (Saudi-Arabia) | Al-Fayha vs Al Riyadh | 0.00 | away_cover | 1.934 | 0.7952 | 0.4978 | 0.2974 | home_cover | -1.0000 |
| 11450 | 2026-05-14T03:00:00 | League One (England) | Stockport County vs Stevenage | -0.50 | away_cover | 1.900 | 0.8064 | 0.5116 | 0.2948 | home_cover | -1.0000 |
| 17022 | 2026-05-14T07:30:00 | Major League Soccer (USA) | New York Red Bulls vs Columbus Crew | 0.00 | away_cover | 1.877 | 0.8141 | 0.5195 | 0.2946 | home_cover | -1.0000 |
| 2198 | 2026-05-17T21:00:00 | Serie A | Inter vs Hellas Verona | -1.25 | home_cover | 1.925 | 0.8023 | 0.5096 | 0.2927 | away_cover | -1.0000 |
| 17730 | 2026-05-21T01:00:00 | 1. Division (Norway) | Asane vs Sandnes ULF | 0.50 | home_cover | 1.877 | 0.8030 | 0.5121 | 0.2909 | home_cover | 0.8770 |
| 16325 | 2026-05-09T13:00:00 | J1 League (Japan) | Mito Hollyhock vs Urawa | 0.50 | home_cover | 1.892 | 0.8051 | 0.5150 | 0.2901 | away_cover | -1.0000 |
| 14407 | 2026-05-23T01:00:00 | Allsvenskan (Sweden) | Djurgardens IF vs IF Brommapojkarna | -1.25 | away_cover | 1.819 | 0.8241 | 0.5347 | 0.2894 | away_cover | 0.8190 |
| 8028 | 2026-05-14T22:30:00 | Super League (Switzerland) | FC Sion vs FC Lugano | -0.50 | away_cover | 1.840 | 0.8184 | 0.5306 | 0.2878 | away_cover | 0.8400 |
| 4330 | 2026-05-09T19:00:00 | 2. Bundesliga (Germany) | Eintracht Braunschweig vs Dynamo Dresden | 0.00 | home_cover | 1.869 | 0.8108 | 0.5243 | 0.2865 | home_cover | 0.8690 |
| 5495 | 2026-05-10T02:00:00 | Ligue 2 (France) | Clermont Foot vs Guingamp | 0.00 | away_cover | 1.884 | 0.7954 | 0.5100 | 0.2854 | home_cover | -1.0000 |
| 7131 | 2026-05-10T01:00:00 | Süper Lig (Turkey) | Gençlerbirliği S.K. vs Kasımpaşa | -0.25 | home_cover | 1.952 | 0.7830 | 0.4977 | 0.2853 | home_cover | 0.9520 |
| 15994 | 2026-05-17T21:00:00 | Superettan (Sweden) | Osters IF vs Ljungskile SK | 0.00 | away_cover | 1.990 | 0.7710 | 0.4863 | 0.2847 | away_cover | 0.9900 |
| 18405 | 2026-05-23T17:00:00 | Liga 1 (Indonesia) | Persib Bandung vs Persijap | -1.75 | home_cover | 1.877 | 0.7909 | 0.5063 | 0.2846 | away_cover | -1.0000 |
| 16995 | 2026-05-03T07:30:00 | Major League Soccer (USA) | New York Red Bulls vs FC Dallas | 0.00 | away_cover | 1.952 | 0.7790 | 0.5000 | 0.2790 | away_cover | 0.9520 |
| 13173 | 2026-05-15T02:00:00 | Pro League (Saudi-Arabia) | Al-Ettifaq vs Al-Ittihad FC | 0.50 | away_cover | 1.990 | 0.7628 | 0.4843 | 0.2785 | away_cover | 0.9900 |
| 18402 | 2026-05-23T17:00:00 | Liga 1 (Indonesia) | Pusamania Borneo vs Malut United | -2.00 | home_cover | 1.806 | 0.8030 | 0.5255 | 0.2775 | home_cover | 0.8060 |
| 8026 | 2026-05-13T02:30:00 | Super League (Switzerland) | Servette FC vs Lausanne | -0.50 | away_cover | 2.050 | 0.7525 | 0.4759 | 0.2766 | home_cover | -1.0000 |
| 15982 | 2026-05-09T23:00:00 | Superettan (Sweden) | GIF Sundsvall vs IFK Norrkoping | 0.50 | away_cover | 1.900 | 0.7852 | 0.5090 | 0.2762 | away_cover | 0.9000 |
| 5192 | 2026-05-18T02:00:00 | Serie B (Italy) | Catanzaro vs Palermo | -0.25 | home_cover | 2.130 | 0.7328 | 0.4580 | 0.2748 | home_cover | 1.1300 |
| 17440 | 2026-05-17T02:45:00 | Premier Division (Ireland) | Sligo Rovers vs Galway United | 0.00 | home_cover | 1.952 | 0.7685 | 0.4955 | 0.2730 | away_cover | -1.0000 |
| 14930 | 2026-05-24T19:35:00 | Super League (China) | Shandong Luneng vs Wuhan Three Towns | -1.25 | away_cover | 1.990 | 0.7613 | 0.4884 | 0.2729 | away_cover | 0.9900 |
| 15695 | 2026-05-25T02:30:00 | Liga Profesional Argentina (Argentina) | River Plate vs Belgrano Cordoba | -0.25 | away_cover | 1.925 | 0.7788 | 0.5070 | 0.2718 | away_cover | 0.9250 |
| 14893 | 2026-05-05T19:00:00 | Super League (China) | Qingdao Youth Island vs Tianjin Teda | -0.50 | home_cover | 2.050 | 0.7456 | 0.4740 | 0.2716 | away_cover | -1.0000 |
| 5180 | 2026-05-09T02:30:00 | Serie B (Italy) | Venezia vs Palermo | -1.25 | away_cover | 1.833 | 0.8010 | 0.5304 | 0.2706 | home_cover | -1.0000 |
| 17057 | 2026-05-24T09:30:00 | Major League Soccer (USA) | Colorado Rapids vs FC Dallas | -0.25 | home_cover | 1.990 | 0.7591 | 0.4907 | 0.2684 | away_cover | -1.0000 |
| 14387 | 2026-05-05T01:00:00 | Allsvenskan (Sweden) | Djurgardens IF vs IFK Goteborg | -0.75 | away_cover | 2.070 | 0.7360 | 0.4687 | 0.2673 | home_cover | -1.0000 |
| 8342 | 2026-05-12T02:00:00 | Liga I (Romania) | FCSB vs Unirea Slobozia | -2.00 | away_cover | 1.952 | 0.7583 | 0.4911 | 0.2672 | away_cover | 0.9520 |
| 16002 | 2026-05-23T21:00:00 | Superettan (Sweden) | United Nordic vs IK brage | -0.25 | home_cover | 1.909 | 0.7720 | 0.5067 | 0.2653 | home_cover | 0.9090 |
| 2511 | 2026-05-18T03:00:00 | Ligue 1 (France) | Marseille vs Rennes | -0.75 | home_cover | 2.070 | 0.7383 | 0.4735 | 0.2648 | home_cover | 1.0700 |
| 17741 | 2026-05-25T23:00:00 | 1. Division (Norway) | Lyn vs Strommen | -0.50 | home_cover | 1.840 | 0.7896 | 0.5258 | 0.2638 | home_cover | 0.8400 |
| 7799 | 2026-05-16T23:00:00 | Bundesliga (Austria) | SCR Altach vs Ried | -0.75 | away_cover | 1.961 | 0.7538 | 0.4910 | 0.2628 | home_cover | -1.0000 |
| 17434 | 2026-05-09T02:45:00 | Premier Division (Ireland) | Shelbourne vs Sligo Rovers | -1.25 | away_cover | 1.813 | 0.7969 | 0.5355 | 0.2614 | away_cover | 0.8130 |
| 16456 | 2026-05-12T18:30:00 | K League 1 (South-Korea) | Incheon United vs Pohang Steelers | 0.25 | away_cover | 2.180 | 0.7067 | 0.4479 | 0.2588 | away_cover | 1.1800 |
| 7586 | 2026-05-03T22:00:00 | Super League 1 (Greece) | OFI vs Aris Thessalonikis | 0.25 | away_cover | 2.029 | 0.7326 | 0.4746 | 0.2580 | away_cover | 1.0290 |
| 13 | 2026-05-24T21:00:00 | Serie A | Parma vs Sassuolo | 0.25 | away_cover | 2.000 | 0.7475 | 0.4904 | 0.2571 | home_cover | -1.0000 |
| 2179 | 2026-05-04T00:00:00 | Serie A | Juventus vs Hellas Verona | -2.00 | home_cover | 2.020 | 0.7381 | 0.4826 | 0.2555 | away_cover | -1.0000 |
| 17561 | 2026-05-08T00:00:00 | Ykkösliiga (Finland) | PK-35 vs MP | -0.50 | home_cover | 2.040 | 0.7270 | 0.4723 | 0.2547 | home_cover | 1.0400 |
| 5188 | 2026-05-13T00:45:00 | Serie B (Italy) | Modena vs Juve Stabia | -0.25 | home_cover | 1.840 | 0.7836 | 0.5306 | 0.2530 | away_cover | -1.0000 |
| 17023 | 2026-05-14T07:30:00 | Major League Soccer (USA) | New England Revolution vs Nashville SC | 0.00 | away_cover | 1.793 | 0.7960 | 0.5441 | 0.2519 | away_cover | 0.7930 |
| 1149 | 2026-05-17T22:00:00 | Premier League | Leeds vs Brighton | 0.25 | away_cover | 1.862 | 0.7779 | 0.5265 | 0.2514 | home_cover | -1.0000 |
| 7611 | 2026-05-22T00:00:00 | Super League 1 (Greece) | Panetolikos vs Asteras Tripolis | -0.25 | away_cover | 1.934 | 0.7492 | 0.4978 | 0.2514 | away_cover | 0.9340 |
| 8348 | 2026-05-19T01:30:00 | Liga I (Romania) | Farul Constanta vs Metaloglobus | -1.75 | away_cover | 1.892 | 0.7578 | 0.5066 | 0.2512 | away_cover | 0.8920 |
| 1502 | 2026-05-11T03:00:00 | La Liga | Barcelona vs Real Madrid | -1.00 | home_cover | 2.060 | 0.7267 | 0.4757 | 0.2510 | home_cover | 1.0600 |
| 8593 | 2026-05-17T23:00:00 | Premier League (Russia) | Krylia Sovetov vs Akron | -0.25 | home_cover | 2.120 | 0.7078 | 0.4582 | 0.2496 | home_cover | 1.1200 |
| 6111 | 2026-05-17T20:30:00 | Eredivisie (Netherlands) | PEC Zwolle vs Feyenoord | 1.25 | away_cover | 2.070 | 0.7177 | 0.4687 | 0.2490 | away_cover | 1.0700 |
| 17729 | 2026-05-21T01:00:00 | 1. Division (Norway) | Strommen vs Haugesund | 0.25 | away_cover | 1.854 | 0.7700 | 0.5215 | 0.2485 | away_cover | 0.8540 |
| 8350 | 2026-05-19T01:30:00 | Liga I (Romania) | Unirea Slobozia vs Uta Arad | 0.00 | away_cover | 1.833 | 0.7735 | 0.5254 | 0.2481 | away_cover | 0.8330 |
| 1506 | 2026-05-13T03:30:00 | La Liga | Osasuna vs Atletico Madrid | 0.00 | away_cover | 1.980 | 0.7399 | 0.4953 | 0.2446 | away_cover | 0.9800 |
| 7373 | 2026-05-17T21:00:00 | Premiership (Scotland) | Dundee vs Aberdeen | 0.00 | away_cover | 1.943 | 0.7398 | 0.4956 | 0.2442 | home_cover | -1.0000 |
| 2492 | 2026-05-03T23:15:00 | Ligue 1 (France) | Strasbourg vs Toulouse | 0.25 | away_cover | 1.961 | 0.7424 | 0.4988 | 0.2436 | away_cover | 0.9610 |
| 16316 | 2026-05-06T12:03:00 | J1 League (Japan) | V-varen Nagasaki vs Fagiano Okayama | 0.00 | home_cover | 2.060 | 0.7133 | 0.4699 | 0.2434 | home_cover | 1.0600 |

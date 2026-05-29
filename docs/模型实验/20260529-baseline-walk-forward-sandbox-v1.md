# Baseline Walk-Forward Recommendation Sandbox v1

- Feature CSV: `local_data\training\baseline_dynamic_features_main_leagues_20260529.csv`
- Scope: `asian_handicap raw_hgb_team_form_plus_all_markets`

## Summary

| Metric | Value |
| --- | ---: |
| Rows | 5330 |
| Folds | 5 |
| Train ratio | 0.6000 |
| Validation ratio | 0.1000 |
| Edge threshold | 0.1000 |
| Candidates | 1266 |
| Profit | 77.3850 |
| ROI | 0.0611 |
| Positive ROI folds | 4 |

## Fold Summary

| Fold | Train | Validation | Bets | Profit | ROI | Positive ROI |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 2502 | 399 | 256 | 5.1990 | 0.0203 | yes |
| 2 | 2490 | 410 | 242 | 28.4780 | 0.1177 | yes |
| 3 | 2487 | 419 | 246 | -1.2310 | -0.0050 | no |
| 4 | 2488 | 415 | 265 | 11.9460 | 0.0451 | yes |
| 5 | 2496 | 434 | 257 | 32.9930 | 0.1284 | yes |

## Side Stability

| Side | Bets | Positive ROI folds | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| home_cover | 656 | 2 | 25.0800 | 0.0382 |
| away_cover | 610 | 5 | 52.3050 | 0.0857 |

## Fold 1 Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| home_cover | 147 | 75 | -0.5970 | -0.0041 |
| away_cover | 109 | 59 | 5.7960 | 0.0532 |

## Fold 1 Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 7103 | 2026-04-19T19:30:00 | Süper Lig (Turkey) | Kasımpaşa vs Alanyaspor | -0.25 | home_cover | 2.150 | 0.9559 | 0.4539 | 0.5020 | home_cover | 1.1500 |
| 14863 | 2026-04-17T19:35:00 | Super League (China) | Chongqing Tongliang Long vs Sichuan Jiuniu | -0.25 | home_cover | 2.000 | 0.9294 | 0.4861 | 0.4433 | home_cover | 1.0000 |
| 17690 | 2026-04-19T23:00:00 | 1. Division (Norway) | Asane vs Strommen | 0.25 | away_cover | 2.090 | 0.8842 | 0.4627 | 0.4215 | away_cover | 1.0900 |
| 11407 | 2026-04-18T22:00:00 | League One (England) | Northampton vs Doncaster | 0.75 | home_cover | 1.877 | 0.9163 | 0.5133 | 0.4030 | away_cover | -1.0000 |
| 11415 | 2026-04-22T02:45:00 | League One (England) | Rotherham vs Luton | 1.00 | home_cover | 1.990 | 0.8748 | 0.4843 | 0.3905 | away_cover | -1.0000 |
| 7780 | 2026-04-23T02:30:00 | Bundesliga (Austria) | Sturm Graz vs Lask Linz | 0.50 | away_cover | 2.100 | 0.8536 | 0.4651 | 0.3885 | home_cover | -1.0000 |
| 16281 | 2026-04-18T14:00:00 | J1 League (Japan) | Tokyo Verdy vs JEF United Chiba | -0.25 | home_cover | 1.869 | 0.9028 | 0.5218 | 0.3810 | home_cover | 0.8690 |
| 1107 | 2026-04-19T03:00:00 | Premier League | Chelsea vs Manchester United | -0.25 | home_cover | 1.869 | 0.9050 | 0.5243 | 0.3807 | away_cover | -1.0000 |
| 11405 | 2026-04-18T22:00:00 | League One (England) | Reading vs Cardiff | 1.00 | away_cover | 2.009 | 0.8401 | 0.4840 | 0.3561 | away_cover | 1.0090 |
| 4004 | 2026-04-22T02:45:00 | Championship (England) | Oxford United vs Wrexham | -0.25 | away_cover | 1.854 | 0.8782 | 0.5263 | 0.3519 | away_cover | 0.8540 |
| 3996 | 2026-04-18T22:00:00 | Championship (England) | Wrexham vs Stoke City | -0.50 | home_cover | 1.877 | 0.8611 | 0.5195 | 0.3416 | home_cover | 0.8770 |
| 13139 | 2026-04-24T23:45:00 | Pro League (Saudi-Arabia) | Al-Fateh vs Al Khaleej Saihat | 0.00 | home_cover | 1.892 | 0.8479 | 0.5090 | 0.3389 | home_cover | 0.8920 |
| 13136 | 2026-04-16T02:00:00 | Pro League (Saudi-Arabia) | Al-Nassr vs Al-Ettifaq | -2.25 | home_cover | 1.833 | 0.8575 | 0.5229 | 0.3346 | away_cover | -1.0000 |
| 15638 | 2026-04-19T04:15:00 | Liga Profesional Argentina (Argentina) | Instituto Cordoba vs Estudiantes L.P. | -0.25 | home_cover | 2.180 | 0.7813 | 0.4479 | 0.3334 | away_cover | -1.0000 |
| 11419 | 2026-04-22T02:45:00 | League One (England) | Stockport County vs Mansfield Town | -1.00 | away_cover | 2.029 | 0.8121 | 0.4795 | 0.3326 | away_cover | 1.0290 |
| 14871 | 2026-04-21T19:35:00 | Super League (China) | Wuhan Three Towns vs Hangzhou Greentown | 0.25 | away_cover | 2.110 | 0.7912 | 0.4603 | 0.3309 | home_cover | -1.0000 |
| 18361 | 2026-04-24T20:00:00 | Liga 1 (Indonesia) | Persib Bandung vs Arema FC | -1.25 | home_cover | 1.877 | 0.8427 | 0.5133 | 0.3294 | away_cover | -1.0000 |
| 14230 | 2026-04-25T00:00:00 | Veikkausliiga (Finland) | SJK vs FF Jaro | -0.50 | home_cover | 1.952 | 0.8214 | 0.5000 | 0.3214 | away_cover | -1.0000 |
| 5768 | 2026-04-19T03:30:00 | Primeira Liga (Portugal) | GIL Vicente vs Guimaraes | -0.50 | home_cover | 2.050 | 0.7961 | 0.4759 | 0.3202 | away_cover | -1.0000 |
| 3988 | 2026-04-18T19:30:00 | Championship (England) | Derby vs Oxford United | -0.50 | away_cover | 1.862 | 0.8426 | 0.5241 | 0.3185 | home_cover | -1.0000 |

## Fold 2 Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| home_cover | 127 | 74 | 18.4130 | 0.1450 |
| away_cover | 115 | 64 | 10.0650 | 0.0875 |

## Fold 2 Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 8574 | 2026-05-01T22:00:00 | Premier League (Russia) | Krylia Sovetov vs Spartak Moscow | 0.75 | home_cover | 1.884 | 0.9147 | 0.5174 | 0.3973 | home_cover | 0.8840 |
| 16439 | 2026-05-02T15:30:00 | K League 1 (South-Korea) | Incheon United vs Gangwon FC | 0.25 | away_cover | 2.140 | 0.8439 | 0.4559 | 0.3880 | away_cover | 1.1400 |
| 7780 | 2026-04-23T02:30:00 | Bundesliga (Austria) | Sturm Graz vs Lask Linz | 0.50 | away_cover | 2.100 | 0.8492 | 0.4651 | 0.3841 | home_cover | -1.0000 |
| 18367 | 2026-04-28T20:00:00 | Liga 1 (Indonesia) | PSBS Biak Numfor vs Malut United | 3.00 | home_cover | 1.813 | 0.8945 | 0.5117 | 0.3828 | away_cover | -1.0000 |
| 18073 | 2026-05-01T01:00:00 | 1. Division (Denmark) | Esbjerg vs AC Horsens | 0.00 | home_cover | 2.080 | 0.8431 | 0.4648 | 0.3783 | away_cover | -1.0000 |
| 2169 | 2026-04-27T00:00:00 | Serie A | Torino vs Inter | 1.25 | home_cover | 2.040 | 0.8557 | 0.4801 | 0.3756 | home_cover | 1.0400 |
| 5777 | 2026-04-26T01:00:00 | Primeira Liga (Portugal) | Benfica vs Moreirense | -2.50 | home_cover | 2.009 | 0.8570 | 0.4830 | 0.3740 | home_cover | 1.0090 |
| 7344 | 2026-04-26T21:00:00 | Premiership (Scotland) | Dundee Utd vs Dundee | -0.25 | home_cover | 1.854 | 0.9014 | 0.5275 | 0.3739 | home_cover | 0.8540 |
| 4751 | 2026-04-27T03:00:00 | Segunda División (Spain) | AD Ceuta FC vs Racing Santander | 0.50 | away_cover | 1.847 | 0.8991 | 0.5285 | 0.3706 | home_cover | -1.0000 |
| 5174 | 2026-05-01T21:00:00 | Serie B (Italy) | Padova vs Pescara | 0.25 | away_cover | 2.140 | 0.8203 | 0.4534 | 0.3669 | home_cover | -1.0000 |
| 5171 | 2026-05-01T21:00:00 | Serie B (Italy) | Spezia vs Venezia | 1.00 | home_cover | 1.826 | 0.8953 | 0.5313 | 0.3640 | home_cover | 0.8260 |
| 6086 | 2026-04-24T03:00:00 | Eredivisie (Netherlands) | PSV Eindhoven vs PEC Zwolle | -1.75 | away_cover | 1.980 | 0.8488 | 0.4887 | 0.3601 | home_cover | -1.0000 |
| 2163 | 2026-04-25T02:45:00 | Serie A | Napoli vs Cremonese | -1.50 | home_cover | 2.050 | 0.8381 | 0.4780 | 0.3601 | home_cover | 1.0500 |
| 14230 | 2026-04-25T00:00:00 | Veikkausliiga (Finland) | SJK vs FF Jaro | -0.50 | home_cover | 1.952 | 0.8496 | 0.5000 | 0.3496 | away_cover | -1.0000 |
| 5482 | 2026-04-25T20:00:00 | Ligue 2 (France) | Grenoble vs Le Mans | 0.50 | home_cover | 2.080 | 0.8140 | 0.4675 | 0.3465 | home_cover | 1.0800 |
| 13139 | 2026-04-24T23:45:00 | Pro League (Saudi-Arabia) | Al-Fateh vs Al Khaleej Saihat | 0.00 | home_cover | 1.892 | 0.8527 | 0.5090 | 0.3437 | home_cover | 0.8920 |
| 6091 | 2026-04-26T18:15:00 | Eredivisie (Netherlands) | Excelsior vs Utrecht | 0.25 | away_cover | 1.961 | 0.8411 | 0.4977 | 0.3434 | home_cover | -1.0000 |
| 16988 | 2026-04-26T10:30:00 | Major League Soccer (USA) | Vancouver Whitecaps vs Colorado Rapids | -1.50 | away_cover | 1.917 | 0.8524 | 0.5093 | 0.3431 | home_cover | -1.0000 |
| 9079 | 2026-04-27T00:00:00 | Superliga (Denmark) | Viborg vs FC Nordsjaelland | -0.25 | away_cover | 1.862 | 0.8635 | 0.5241 | 0.3394 | home_cover | -1.0000 |
| 16309 | 2026-05-02T14:00:00 | J1 League (Japan) | Gamba Osaka vs Vissel Kobe | 0.25 | away_cover | 2.000 | 0.8272 | 0.4884 | 0.3388 | home_cover | -1.0000 |

## Fold 3 Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| home_cover | 153 | 78 | -1.7940 | -0.0117 |
| away_cover | 93 | 48 | 0.5630 | 0.0061 |

## Fold 3 Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 18367 | 2026-04-28T20:00:00 | Liga 1 (Indonesia) | PSBS Biak Numfor vs Malut United | 3.00 | home_cover | 1.813 | 0.9693 | 0.5117 | 0.4576 | away_cover | -1.0000 |
| 15668 | 2026-05-03T03:15:00 | Liga Profesional Argentina (Argentina) | Central Cordoba de Santiago vs Boca Juniors | 0.50 | home_cover | 2.060 | 0.8996 | 0.4681 | 0.4315 | away_cover | -1.0000 |
| 15188 | 2026-05-03T03:00:00 | Serie A (Brazil) | Botafogo vs Remo | -1.00 | home_cover | 2.040 | 0.8918 | 0.4801 | 0.4117 | away_cover | -1.0000 |
| 15189 | 2026-05-03T05:30:00 | Serie A (Brazil) | Palmeiras vs Santos | -1.00 | home_cover | 2.130 | 0.8547 | 0.4598 | 0.3949 | away_cover | -1.0000 |
| 11435 | 2026-04-29T02:45:00 | League One (England) | Stockport County vs Port Vale | -1.50 | away_cover | 1.917 | 0.8836 | 0.5022 | 0.3814 | away_cover | 0.9170 |
| 4032 | 2026-05-02T19:30:00 | Championship (England) | Portsmouth vs Birmingham | 0.50 | away_cover | 2.050 | 0.8550 | 0.4740 | 0.3810 | home_cover | -1.0000 |
| 7584 | 2026-05-03T00:30:00 | Super League 1 (Greece) | Asteras Tripolis vs Atromitos | -0.50 | home_cover | 1.952 | 0.8702 | 0.4933 | 0.3769 | home_cover | 0.9520 |
| 16438 | 2026-05-02T15:30:00 | K League 1 (South-Korea) | Jeju United FC vs Jeonbuk Motors | 0.25 | away_cover | 1.877 | 0.8946 | 0.5195 | 0.3751 | away_cover | 0.8770 |
| 14238 | 2026-05-03T00:00:00 | Veikkausliiga (Finland) | AC Oulu vs KuPS | 0.25 | away_cover | 2.070 | 0.8458 | 0.4715 | 0.3743 | home_cover | -1.0000 |
| 16323 | 2026-05-06T16:00:00 | J1 League (Japan) | Kawasaki Frontale vs Tokyo Verdy | -0.25 | home_cover | 1.847 | 0.9014 | 0.5285 | 0.3729 | home_cover | 0.8470 |
| 5169 | 2026-05-01T21:00:00 | Serie B (Italy) | Bari vs Virtus Entella | 0.00 | home_cover | 2.120 | 0.8295 | 0.4582 | 0.3713 | home_cover | 1.1200 |
| 1804 | 2026-05-02T21:30:00 | Bundesliga (Germany) | Bayern München vs 1. FC Heidenheim | -2.00 | home_cover | 2.020 | 0.8523 | 0.4836 | 0.3687 | away_cover | -1.0000 |
| 2491 | 2026-05-03T21:00:00 | Ligue 1 (France) | Lille vs Le Havre | -1.25 | home_cover | 1.892 | 0.8855 | 0.5188 | 0.3667 | away_cover | -1.0000 |
| 15194 | 2026-05-04T03:00:00 | Serie A (Brazil) | Flamengo vs Vasco DA Gama | -1.25 | home_cover | 2.080 | 0.8363 | 0.4713 | 0.3650 | away_cover | -1.0000 |
| 8334 | 2026-05-05T01:30:00 | Liga I (Romania) | Rapid vs CFR 1907 Cluj | -0.25 | home_cover | 2.060 | 0.8311 | 0.4681 | 0.3630 | away_cover | -1.0000 |
| 5180 | 2026-05-09T02:30:00 | Serie B (Italy) | Venezia vs Palermo | -1.25 | away_cover | 1.833 | 0.8893 | 0.5304 | 0.3589 | home_cover | -1.0000 |
| 15678 | 2026-05-05T04:00:00 | Liga Profesional Argentina (Argentina) | Gimnasia M. vs Defensa Y Justicia | 0.00 | home_cover | 1.751 | 0.9009 | 0.5477 | 0.3532 | home_cover | 0.7510 |
| 16999 | 2026-05-03T08:30:00 | Major League Soccer (USA) | Houston Dynamo vs Colorado Rapids | -0.50 | home_cover | 1.970 | 0.8476 | 0.4954 | 0.3522 | home_cover | 0.9700 |
| 6097 | 2026-05-03T18:15:00 | Eredivisie (Netherlands) | FC Volendam vs Heerenveen | 0.25 | away_cover | 1.961 | 0.8433 | 0.4977 | 0.3456 | away_cover | 0.9610 |
| 14891 | 2026-05-02T19:35:00 | Super League (China) | Hangzhou Greentown vs Sichuan Jiuniu | -0.25 | home_cover | 1.943 | 0.8451 | 0.5000 | 0.3451 | home_cover | 0.9430 |

## Fold 4 Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| away_cover | 163 | 91 | 13.1620 | 0.0807 |
| home_cover | 102 | 52 | -1.2160 | -0.0119 |

## Fold 4 Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 8027 | 2026-05-14T22:30:00 | Super League (Switzerland) | FC Basel 1893 vs FC ST. Gallen | -0.50 | away_cover | 1.961 | 0.9036 | 0.4977 | 0.4059 | away_cover | 0.9610 |
| 13158 | 2026-05-05T02:00:00 | Pro League (Saudi-Arabia) | Al-Ittihad FC vs Al Kholood | -0.75 | away_cover | 1.862 | 0.9164 | 0.5166 | 0.3998 | away_cover | 0.8620 |
| 2185 | 2026-05-10T00:00:00 | Serie A | Lazio vs Inter | 0.50 | home_cover | 2.080 | 0.8602 | 0.4713 | 0.3889 | away_cover | -1.0000 |
| 14669 | 2026-05-16T08:00:00 | Primera División (Chile) | Palestino vs D. La Serena | -0.50 | home_cover | 2.040 | 0.8634 | 0.4761 | 0.3873 | home_cover | 1.0400 |
| 1828 | 2026-05-16T21:30:00 | Bundesliga (Germany) | 1. FC Heidenheim vs FSV Mainz 05 | -0.50 | home_cover | 2.050 | 0.8543 | 0.4789 | 0.3754 | away_cover | -1.0000 |
| 4331 | 2026-05-10T02:30:00 | 2. Bundesliga (Germany) | 1. FC Nürnberg vs FC Schalke 04 | 0.00 | away_cover | 2.040 | 0.8512 | 0.4761 | 0.3751 | home_cover | -1.0000 |
| 16323 | 2026-05-06T16:00:00 | J1 League (Japan) | Kawasaki Frontale vs Tokyo Verdy | -0.25 | home_cover | 1.847 | 0.9034 | 0.5285 | 0.3749 | home_cover | 0.8470 |
| 2502 | 2026-05-11T03:00:00 | Ligue 1 (France) | Auxerre vs Nice | -0.25 | home_cover | 2.110 | 0.8394 | 0.4648 | 0.3746 | home_cover | 1.1100 |
| 4770 | 2026-05-10T20:00:00 | Segunda División (Spain) | FC Andorra vs Las Palmas | 0.00 | away_cover | 1.934 | 0.8756 | 0.5046 | 0.3710 | home_cover | -1.0000 |
| 15985 | 2026-05-13T01:00:00 | Superettan (Sweden) | Landskrona BoIS vs Norrby IF | -0.50 | away_cover | 1.854 | 0.8908 | 0.5215 | 0.3693 | away_cover | 0.8540 |
| 18380 | 2026-05-05T16:30:00 | Liga 1 (Indonesia) | Persepam Madura Utd vs Bali United | -0.25 | away_cover | 1.813 | 0.8876 | 0.5307 | 0.3569 | home_cover | -1.0000 |
| 1493 | 2026-05-05T03:00:00 | La Liga | Sevilla vs Real Sociedad | -0.25 | home_cover | 2.080 | 0.8249 | 0.4713 | 0.3536 | home_cover | 1.0800 |
| 8891 | 2026-05-16T02:30:00 | Ekstraklasa (Poland) | Korona Kielce vs Widzew Łódź | -0.25 | home_cover | 2.130 | 0.8082 | 0.4562 | 0.3520 | home_cover | 1.1300 |
| 2189 | 2026-05-10T21:00:00 | Serie A | Cremonese vs Pisa | -0.50 | away_cover | 1.980 | 0.8432 | 0.4953 | 0.3479 | home_cover | -1.0000 |
| 13169 | 2026-05-13T00:20:00 | Pro League (Saudi-Arabia) | Al Kholood vs Al Okhdood | -1.00 | away_cover | 2.060 | 0.8115 | 0.4671 | 0.3444 | away_cover | 1.0600 |
| 13167 | 2026-05-12T00:50:00 | Pro League (Saudi-Arabia) | NEOM vs Al Shabab | -0.25 | away_cover | 1.917 | 0.8455 | 0.5022 | 0.3433 | home_cover | -1.0000 |
| 7602 | 2026-05-14T00:30:00 | Super League 1 (Greece) | PAOK vs AEK Athens FC | -0.50 | away_cover | 1.917 | 0.8447 | 0.5022 | 0.3425 | away_cover | 0.9170 |
| 9091 | 2026-05-10T22:00:00 | Superliga (Denmark) | Silkeborg vs FC Copenhagen | 1.00 | home_cover | 1.840 | 0.8722 | 0.5306 | 0.3416 | away_cover | -1.0000 |
| 16661 | 2026-05-10T18:00:00 | K League 2 (South-Korea) | Gyeongnam FC vs Gimhae City | -0.25 | home_cover | 1.909 | 0.8417 | 0.5055 | 0.3362 | home_cover | 0.9090 |
| 16333 | 2026-05-10T15:00:00 | J1 League (Japan) | Nagoya Grampus vs Kyoto Sanga | -0.50 | away_cover | 1.925 | 0.8430 | 0.5070 | 0.3360 | home_cover | -1.0000 |

## Fold 5 Side Summary

| Side | Bets | Wins | Profit | ROI |
| --- | ---: | ---: | ---: | ---: |
| away_cover | 130 | 79 | 22.7190 | 0.1748 |
| home_cover | 127 | 70 | 10.2740 | 0.0809 |

## Fold 5 Candidate Detail

| Match | Kickoff | League | Fixture | Line | Side | Odds | Model p | Market p | Edge | Actual | Profit |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 18396 | 2026-05-17T16:30:00 | Liga 1 (Indonesia) | Bali United vs Bhayangkara FC | -0.50 | home_cover | 2.040 | 0.9115 | 0.4723 | 0.4392 | home_cover | 1.0400 |
| 2205 | 2026-05-25T02:45:00 | Serie A | Torino vs Juventus | 1.00 | home_cover | 2.040 | 0.9148 | 0.4801 | 0.4347 | home_cover | 1.0400 |
| 1828 | 2026-05-16T21:30:00 | Bundesliga (Germany) | 1. FC Heidenheim vs FSV Mainz 05 | -0.50 | home_cover | 2.050 | 0.9114 | 0.4789 | 0.4325 | away_cover | -1.0000 |
| 7602 | 2026-05-14T00:30:00 | Super League 1 (Greece) | PAOK vs AEK Athens FC | -0.50 | away_cover | 1.917 | 0.9316 | 0.5022 | 0.4294 | away_cover | 0.9170 |
| 8593 | 2026-05-17T23:00:00 | Premier League (Russia) | Krylia Sovetov vs Akron | -0.25 | home_cover | 2.120 | 0.8854 | 0.4582 | 0.4272 | home_cover | 1.1200 |
| 17027 | 2026-05-14T08:30:00 | Major League Soccer (USA) | FC Dallas vs Vancouver Whitecaps | 0.50 | away_cover | 1.961 | 0.9154 | 0.4977 | 0.4177 | away_cover | 0.9610 |
| 17718 | 2026-05-16T00:00:00 | 1. Division (Norway) | Sandnes ULF vs Egersund | 0.25 | away_cover | 2.000 | 0.8929 | 0.4831 | 0.4098 | home_cover | -1.0000 |
| 17034 | 2026-05-17T04:30:00 | Major League Soccer (USA) | CF Montreal vs Chicago Fire | 0.25 | home_cover | 1.847 | 0.9326 | 0.5285 | 0.4041 | away_cover | -1.0000 |
| 14253 | 2026-05-20T23:00:00 | Veikkausliiga (Finland) | Ilves vs Inter Turku | 0.25 | away_cover | 1.990 | 0.8890 | 0.4874 | 0.4016 | away_cover | 0.9900 |
| 14673 | 2026-05-18T00:30:00 | Primera División (Chile) | Huachipato vs Union La Calera | -0.25 | home_cover | 2.100 | 0.8617 | 0.4633 | 0.3984 | home_cover | 1.1000 |
| 14669 | 2026-05-16T08:00:00 | Primera División (Chile) | Palestino vs D. La Serena | -0.50 | home_cover | 2.040 | 0.8709 | 0.4761 | 0.3948 | home_cover | 1.0400 |
| 14037 | 2026-05-16T22:00:00 | Eliteserien (Norway) | Fredrikstad vs Ham-Kam | -0.50 | home_cover | 2.060 | 0.8681 | 0.4757 | 0.3924 | home_cover | 1.0600 |
| 14258 | 2026-05-23T22:00:00 | Veikkausliiga (Finland) | Ilves vs Gnistan | -0.25 | home_cover | 1.917 | 0.8924 | 0.5093 | 0.3831 | home_cover | 0.9170 |
| 5195 | 2026-05-23T02:00:00 | Serie B (Italy) | Sudtirol vs Bari | -0.50 | away_cover | 2.040 | 0.8561 | 0.4782 | 0.3779 | away_cover | 1.0400 |
| 16462 | 2026-05-17T15:30:00 | K League 1 (South-Korea) | Jeju United FC vs FC Anyang | -0.25 | away_cover | 1.840 | 0.9049 | 0.5306 | 0.3743 | away_cover | 0.8400 |
| 8891 | 2026-05-16T02:30:00 | Ekstraklasa (Poland) | Korona Kielce vs Widzew Łódź | -0.25 | home_cover | 2.130 | 0.8234 | 0.4562 | 0.3672 | home_cover | 1.1300 |
| 2207 | 2026-05-25T02:45:00 | Serie A | Cremonese vs Como | 1.00 | home_cover | 1.934 | 0.8693 | 0.5072 | 0.3621 | away_cover | -1.0000 |
| 16352 | 2026-05-24T11:55:00 | J1 League (Japan) | Fagiano Okayama vs Cerezo Osaka | 0.00 | away_cover | 1.917 | 0.8650 | 0.5068 | 0.3582 | away_cover | 0.9170 |
| 1152 | 2026-05-20T02:30:00 | Premier League | Bournemouth vs Manchester City | 0.75 | home_cover | 2.100 | 0.8190 | 0.4670 | 0.3520 | home_cover | 1.1000 |
| 14923 | 2026-05-20T20:00:00 | Super League (China) | Hangzhou Greentown vs Shandong Luneng | 0.00 | away_cover | 1.869 | 0.8682 | 0.5194 | 0.3488 | home_cover | -1.0000 |

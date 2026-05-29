# 全主联赛训练数据审计

- 日期: 2026-05-29
- 数据库: `local_data/icewine_prediction.sqlite3`
- 主训练口径: `leagues.is_enabled = 1`，排除欧冠/欧联/欧协联，已完赛且有比分，`kickoff_time >= 2026-01-15 00:00:00`。
- 赔率口径: OddsPapi + Pinnacle，要求 `asian_handicap`、`total_goals`、`match_winner` 三市场都有主快照。
- 欧战口径: 只作为赛果辅助数据，不纳入本轮赔率训练样本。

## 总览

| 指标 | 数值 |
| --- | ---: |
| Eligible 主联赛比赛 | 5981 |
| 完整三市场比赛 | 5330 |
| 三市场覆盖率 | 89.1% |
| Asian handicap 覆盖 | 5330 (89.1%) |
| Total goals 覆盖 | 5330 (89.1%) |
| Match winner 覆盖 | 5330 (89.1%) |
| 主快照总数 | 786337 |
| success / empty / unavailable / none | 5330 / 456 / 95 / 100 |
| unmatched / failed | 0 / 0 |

## 按赛季

| Season | Eligible | 完整三市场 | 覆盖率 | success | empty | unavailable | none |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 4278 | 3707 | 86.7% | 3707 | 415 | 59 | 97 |
| 2026 | 1703 | 1623 | 95.3% | 1623 | 41 | 36 | 3 |

## 新增五个主联赛

新增五个主联赛合计 eligible `433`，完整三市场 `360`，覆盖率 `83.1%`。

| ID | 联赛 | Eligible | 完整三市场 | 覆盖率 | empty | unavailable | none |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 120 | 1. Division (Denmark) | 78 | 69 | 88.5% | 0 | 9 | 0 |
| 104 | 1. Division (Norway) | 71 | 61 | 85.9% | 0 | 10 | 0 |
| 274 | Liga 1 (Indonesia) | 153 | 117 | 76.5% | 11 | 25 | 0 |
| 357 | Premier Division (Ireland) | 91 | 84 | 92.3% | 1 | 6 | 0 |
| 1087 | Ykkosliiga (Finland) | 40 | 29 | 72.5% | 0 | 11 | 0 |

## 覆盖率低于 80% 的主联赛

| ID | 联赛 | Eligible | 完整三市场 | 覆盖率 | empty | unavailable | none |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1087 | Ykkosliiga (Finland) | 40 | 29 | 72.5% | 0 | 11 | 0 |
| 274 | Liga 1 (Indonesia) | 153 | 117 | 76.5% | 11 | 25 | 0 |
| 89 | Eerste Divisie (Netherlands) | 181 | 139 | 76.8% | 20 | 11 | 11 |

## 按主联赛明细

| ID | 联赛 | 国家 | Eligible | 完整三市场 | 覆盖率 | success | empty | unavailable | none | 快照 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 128 | Liga Profesional Argentina (Argentina) | Argentina | 255 | 230 | 90.2% | 230 | 21 | 1 | 3 | 34367 |
| 41 | League One (England) | England | 265 | 226 | 85.3% | 226 | 19 | 0 | 20 | 31335 |
| 253 | Major League Soccer (USA) | USA | 218 | 218 | 100.0% | 218 | 0 | 0 | 0 | 32434 |
| 40 | Championship (England) | England | 249 | 216 | 86.7% | 216 | 31 | 2 | 0 | 31509 |
| 141 | Segunda Division (Spain) | Spain | 209 | 176 | 84.2% | 176 | 25 | 1 | 7 | 26455 |
| 136 | Serie B (Italy) | Italy | 198 | 173 | 87.4% | 173 | 19 | 6 | 0 | 25639 |
| 98 | J1 League (Japan) | Japan | 180 | 172 | 95.6% | 172 | 2 | 6 | 0 | 25970 |
| 140 | La Liga | Spain | 191 | 167 | 87.4% | 167 | 17 | 0 | 7 | 25217 |
| 71 | Serie A (Brazil) | Brazil | 167 | 163 | 97.6% | 163 | 4 | 0 | 0 | 24492 |
| 135 | Serie A | Italy | 184 | 154 | 83.7% | 154 | 18 | 0 | 12 | 23254 |
| 39 | Premier League | England | 170 | 153 | 90.0% | 153 | 17 | 0 | 0 | 23103 |
| 307 | Pro League (Saudi-Arabia) | Saudi-Arabia | 182 | 150 | 82.4% | 150 | 12 | 0 | 20 | 22408 |
| 78 | Bundesliga (Germany) | Germany | 162 | 140 | 86.4% | 140 | 22 | 0 | 0 | 21140 |
| 89 | Eerste Divisie (Netherlands) | Netherlands | 181 | 139 | 76.8% | 139 | 20 | 11 | 11 | 19774 |
| 79 | 2. Bundesliga (Germany) | Germany | 154 | 135 | 87.7% | 135 | 19 | 0 | 0 | 20264 |
| 144 | Jupiler Pro League (Belgium) | Belgium | 153 | 135 | 88.2% | 135 | 18 | 0 | 0 | 20143 |
| 61 | Ligue 1 (France) | France | 154 | 134 | 87.0% | 134 | 20 | 0 | 0 | 20234 |
| 94 | Primeira Liga (Portugal) | Portugal | 154 | 133 | 86.4% | 133 | 15 | 0 | 6 | 19841 |
| 203 | Super Lig (Turkey) | Turkey | 153 | 132 | 86.3% | 132 | 18 | 0 | 3 | 19932 |
| 106 | Ekstraklasa (Poland) | Poland | 137 | 131 | 95.6% | 131 | 6 | 0 | 0 | 19294 |
| 88 | Eredivisie (Netherlands) | Netherlands | 148 | 128 | 86.5% | 128 | 16 | 4 | 0 | 19328 |
| 283 | Liga I (Romania) | Romania | 145 | 128 | 88.3% | 128 | 17 | 0 | 0 | 18237 |
| 62 | Ligue 2 (France) | France | 145 | 126 | 86.9% | 126 | 18 | 1 | 0 | 18905 |
| 274 | Liga 1 (Indonesia) | Indonesia | 153 | 117 | 76.5% | 117 | 11 | 25 | 0 | 17543 |
| 169 | Super League (China) | China | 112 | 112 | 100.0% | 112 | 0 | 0 | 0 | 16912 |
| 197 | Super League 1 (Greece) | Greece | 125 | 109 | 87.2% | 109 | 14 | 0 | 2 | 16338 |
| 207 | Super League (Switzerland) | Switzerland | 118 | 100 | 84.7% | 100 | 14 | 0 | 4 | 14979 |
| 293 | K League 2 (South-Korea) | South-Korea | 104 | 99 | 95.2% | 99 | 5 | 0 | 0 | 9972 |
| 235 | Premier League (Russia) | Russia | 99 | 99 | 100.0% | 99 | 0 | 0 | 0 | 14949 |
| 265 | Primera Division (Chile) | Chile | 103 | 98 | 95.1% | 98 | 5 | 0 | 0 | 14191 |
| 179 | Premiership (Scotland) | Scotland | 104 | 90 | 86.5% | 90 | 11 | 0 | 3 | 13325 |
| 218 | Bundesliga (Austria) | Austria | 92 | 89 | 96.7% | 89 | 3 | 0 | 0 | 13318 |
| 292 | K League 1 (South-Korea) | South-Korea | 90 | 89 | 98.9% | 89 | 1 | 0 | 0 | 13318 |
| 357 | Premier Division (Ireland) | Ireland | 91 | 84 | 92.3% | 84 | 1 | 6 | 0 | 12563 |
| 119 | Superliga (Denmark) | Denmark | 85 | 82 | 96.5% | 82 | 3 | 0 | 0 | 12261 |
| 188 | A-League (Australia) | Australia | 90 | 76 | 84.4% | 76 | 12 | 0 | 2 | 11355 |
| 103 | Eliteserien (Norway) | Norway | 76 | 76 | 100.0% | 76 | 0 | 0 | 0 | 11476 |
| 113 | Allsvenskan (Sweden) | Sweden | 72 | 71 | 98.6% | 71 | 0 | 1 | 0 | 10475 |
| 114 | Superettan (Sweden) | Sweden | 72 | 70 | 97.2% | 70 | 1 | 1 | 0 | 10083 |
| 120 | 1. Division (Denmark) | Denmark | 78 | 69 | 88.5% | 69 | 0 | 9 | 0 | 10053 |
| 104 | 1. Division (Norway) | Norway | 71 | 61 | 85.9% | 61 | 0 | 10 | 0 | 8113 |
| 244 | Veikkausliiga (Finland) | Finland | 52 | 51 | 98.1% | 51 | 1 | 0 | 0 | 7580 |
| 1087 | Ykkosliiga (Finland) | Finland | 40 | 29 | 72.5% | 29 | 0 | 11 | 0 | 4258 |

## 欧战赛果辅助数据

| ID | 赛事 | Season | 总场次 | 已完赛有比分 | 首场 | 末场 |
| ---: | --- | ---: | ---: | ---: | --- | --- |
| 2 | UEFA Champions League (World) | 2025 | 281 | 280 | 2025-07-08 23:00:00.000000 | 2026-05-31 00:00:00.000000 |
| 3 | UEFA Europa League (World) | 2025 | 271 | 271 | 2025-07-11 00:00:00.000000 | 2026-05-21 03:00:00.000000 |
| 848 | UEFA Europa Conference League (World) | 2025 | 409 | 409 | 2025-07-09 00:00:00.000000 | 2026-05-28 03:00:00.000000 |

## 结论

- 当前主训练池可以先使用 `5330` 场完整三市场比赛作为 baseline 样本。
- 新增五个主联赛贡献 `360` 场完整三市场样本，已与其他主联赛同等纳入。
- 当前没有 `unmatched` 或 `failed` 残留；剩余缺口主要是 `empty` 和 OddsPapi `unavailable/404`。
- `none=100` 主要来自尚未继续补跑或刻意未补的 enabled 联赛窗口；下一步训练 baseline 可以先过滤掉非完整三市场比赛。
- 欧战赛果已经可作为未来赛程/状态辅助特征来源，但本轮不进入赔率训练样本。

# 芬超冠军组 23442 OddsPapi 映射核查

2026-10-28 北京时间 12:24 开始只读实查。结论：目标比赛无需新增阶段映射，现有 `244 -> 41` 可完成赛事匹配和历史赔率读取。未修改生产代码或数据库。

## 目标比赛

- matchID：23442；API-Football fixture ID：1638113。
- 芬超，奥卢（AC Oulu）对 VPS瓦萨（VPS）。
- 轮次：`Championship Group - 30`。
- 北京时间：2026-10-29 00:00；对应 UTC 2026-10-28 16:00。
- OddsPapi：`id1000004174299706`，tournamentId=41，tournamentName=Veikkausliiga。
- 实查状态：Pre-Game（statusId=0），hasOdds=true。

## 真实调用链与结果

复用项目 `resolve_oddspapi_tournament_id`、`OddsPapiSyncClient.fetch_fixtures`、`find_best_odds_source_match` 及现有全局球队别名；未覆盖映射值。诊断请求使用系统 requests.Session，未修改生产默认网络配置。

1. 现有解析器返回 41。赛事查询窗口为 UTC 2026-10-28 14:00–18:00。
2. 首次 fixtures 请求附带 statusId=2 和 hasOdds=true，返回 HTTP 404。目标比赛仍是赛前状态，受完赛筛选条件排除。
3. 客户端已有 404 回退逻辑，移除 statusId/hasOdds，保留 tournamentId=41 和相同时间窗，再次查询成功。
4. 现有球队别名可将 VPS 匹配到 Vaasan Palloseura；匹配置信度为 1.0000，开球时间差为 0。
5. 使用项目订阅标识 pinnacle+30 请求 historical-odds 成功，返回 86 个原始市场、3052 条原始价格变更记录。这不是入库标准快照数，也不代表未来临场时间点已覆盖。

本次共使用 3 次 API 请求。无需像爱甲那样更换阶段赛事 ID；首次筛选产生的 404 已被正常回退处理。

## 本地历史对照

本季冠军组第 23–29 轮，每轮 3 场，共 21 场 OddsPapi 源状态均为 success。近期保级组和附加赛也有成功记录。以上仅用于核对现有阶段采集，不推断所有未来阶段的归属。

23442 在本次核查前没有 odds_source_matches、data_sync_run_items 或 historical_odds_snapshots 记录，因此目前属于尚未有采集记录，不能称为已拉取失败。本次仅核查，未补采入库。

## 代码与证据

- 默认映射：`src/icewine_prediction/oddspapi_sync_runner.py`，API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS 中 `244: 41`。
- 阶段解析：`src/icewine_prediction/odds_source_match_service.py`，resolve_oddspapi_tournament_id；芬超走默认映射。
- 已有筛选回退：`src/icewine_prediction/oddspapi_sync_runner.py`，OddsPapiSyncClient.fetch_fixtures。
- 实际 API 参数、响应、匹配结果及摘要：`.tmp/finland_23442_probe_20261028.json`（不含 API 密钥）。

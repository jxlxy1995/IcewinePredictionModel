# 墨西超 OddsPapi 阶段映射修复

## 原因与修复

官方 v4/tournaments 实查：27464 为 liga-mx-apertura，27466 为 liga-mx-clausura。API-Football 的 262 合并两阶段，而本项目此前只映射到 27466，导致 2026 年 Apertura 比赛查询 404。并非墨西超整体没有 OddsPapi 数据。

官方 fixtures 对照验证：2026-10-26 的美洲队—帕丘卡等三场在 27464 下返回正常；同时间段查询 27466 返回 404。美洲队—帕丘卡 OddsPapi fixtureId 为 id1002746472055274。

新增 resolve_oddspapi_tournament_id：优先使用 league_round 中 Apertura/Clausura，缺失时按墨西哥城当地月份回退（7–12月 Apertura，1–6月 Clausura）。轮次优先确保延期比赛不会仅因跨月而选错阶段。主同步、probe、diagnostics、匹配校验共用同一解析函数。其他联赛和全局网络设置不变。

## 实际恢复

| 比赛 ID | 新增 OddsPapi 主表赔率 | 保留 The Odds API 赔率 | 综合标准时间点覆盖 |
|---:|---:|---:|---:|
| 23410 | 302 | 42 | 18/18 |
| 23411 | 37 | 42 | 18/18 |
| 23409 | 58 | 42 | 18/18 |
| 23408 | 58 | 42 | 18/18 |
| 23331 | 302 | 42 | 18/18 |
| 23329 | 302 | 42 | 18/18 |
| 23328 | 55 | 42 | 18/18 |
| 23207 | 308 | 42 | 18/18 |
| 23206 | 304 | 42 | 18/18 |
| 合计 | 1726 | 378 | 9 场全部覆盖 |

以上为最近一轮 9 场。各场源记录均为 success；原始邻近盘口表也按既有同步流程保存。部分比赛 Oddspapi 自身时间点仍不齐，综合覆盖由现存 The Odds API 补充，不等于每场 Oddspapi 独立覆盖 18/18。

2026 赛季全库现为 oddspapi 9 场/1726 条，The Odds API 124 场/5208 条。未启动其余全赛季历史补采。

## 旧失败状态

普通批量采集会跳过 unavailable。对本季 Apertura、空 fixture ID、错误恰为 HTTP 404、没有 Oddspapi 赔率的 70 条记录，先完整备份，再改为可重试的 fixture_lookup_failed，并在错误信息中保留原错误及阶段修复原因。

备份：`.tmp/mexico_stale_404_before_requeue.json`。已恢复的 9 场同步前状态分别保存在 `.tmp/mexico_recovery_before_*.json`。恢复脚本为 `.tmp/recover_mexico_oddspapi.py`，显式 match_ids 可以重试旧失败记录，设有请求预算、间隔与其他源记录数校验。

当前本季 Oddspapi 状态：9 success、72 fixture_lookup_failed（含 70 条重新排队记录与此前 2 条连接失败）。这 72 条不是新发起的 72 次失败，不应把重排状态当成新请求结果。

## 验证与运行状态

- 新增 14 项回归测试，修复前 7 失败，修复后全部通过。
- 相关 tests/test_odds_source_match_service.py、test_oddspapi_sync_runner.py、test_oddspapi_diagnostic_service.py、test_oddspapi_batch_backfill_service.py：113 passed，1 deselected。
- 被排除的原有 test_run_oddspapi_sync_for_session_preserves_execution_timepoints_after_sampling 期待 3 条实际 4 条；以 git HEAD 原代码单独重跑也失败，属于基线问题，未在本任务修改。
- git diff --check 通过；数据库只读复核确认 9 场恢复、原 378 条其他源赔率保留、旧 unavailable 清除。
- 网页后端在确认无运行中同步/自动任务后重载，PID 30548，/api/health 返回 200。前端未重启。
- 本次提交仅包含墨西超阶段映射修复、回归测试、实施计划与本报告；用户原有 config/display_names.yaml 与其他交接文档变更未覆盖。

诊断过程中强制直连出现连接重置，默认 requests 会话能够访问但也有偶发超时、SSL/ProxyError；仅本次恢复脚本使用系统默认网络会话，没有修改生产客户端的 trust_env=False 行为。首次部分比赛失败后有界重试，最终本轮 9 场成功。这一环境网络现象与原阶段映射 404 分开记录。

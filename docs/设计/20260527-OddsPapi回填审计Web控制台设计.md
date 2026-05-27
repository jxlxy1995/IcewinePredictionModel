# OddsPapi 回填审计 Web 控制台设计

日期：`2026-05-27`

## 目标

把已有的 OddsPapi 回填审计能力接入 Web 控制台，提供一个只读状态页，方便人工在后台脚本运行中或运行结束后查看当前回填进度、联赛覆盖情况和失败分布。

## 范围

本次只做展示层接入：

- 新增后端接口 `GET /api/oddspapi/backfill-audit?season=2025`。
- 新增前端导航页 `回填审计`。
- 展示 worker 当前联赛、轮次、已处理比赛、写入快照、失败数、请求数。
- 展示联赛级审计表：完赛数、已匹配数、有快照比赛数、快照总数、亚盘/大小球快照数、状态分布、主要失败原因。
- 联赛名优先使用中文展示名，底层仍保留英文原名和 OddsPapi ID。

## 非目标

- 不启动、停止或重启 worker。
- 不调用 OddsPapi API。
- 不运行 fixture 诊断。
- 不写入 `config/external_aliases.yaml`。
- 不修改 `odds_source_matches` 或历史赔率快照。

## 后端设计

后端复用 `oddspapi_backfill_audit_service.build_oddspapi_backfill_audit_for_session` 的统计逻辑，并在 `web_api.py` 中增加轻量序列化层：

- `worker_progress`：来自 `logs/odds/oddspapi-worker-progress.json`。
- `league_summaries`：来自数据库中的 `matches`、`odds_source_matches`、`historical_odds_snapshots` 聚合。
- `display_name_service`：沿用 Web API 初始化时的中文名服务。

接口返回结构保持前端友好，不返回 Markdown 文本报告。

## 前端设计

前端新增 `oddspapiBackfillAuditWorkspace.ts`，把展示计算从 React 页面里拆出：

- `buildOddspapiAuditSummaryCards`：生成顶部汇总卡片。
- `listOddspapiLeagueAuditRows`：补充覆盖率、问题数、状态摘要和主要失败原因，并按问题数降序排序。
- `formatOddspapiStatusLabel`：把 `success`、`unmatched`、`empty`、`unavailable`、`failed` 等状态转换为界面文案。

`DashboardPage` 只负责布局和渲染，不直接承载统计规则。

## 后续扩展

后续如果要继续接 Web，可以在同一个页面下面分区追加：

- fixture 诊断报告列表。
- 别名候选建议预览。
- 手动确认后的别名写入入口。

这些操作都应先保持显式人工确认，避免 Web 页误触影响正式回填策略。

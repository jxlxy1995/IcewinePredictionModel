# OddsPapi fixture 匹配诊断设计

## 背景

OddsPapi 历史赔率回填最容易卡在本地比赛和 OddsPapi fixture 的映射阶段。API-Football 与 OddsPapi 没有共用 fixture id，因此不能把 API-Football 的 `fixture_id` 直接用于 OddsPapi，只能通过联赛映射、开球时间窗口、主客队名称和别名进行本地匹配。

本设计用于协助回填侧排错：脚本可以独立跑完并输出报告，后续人工查看报告后再决定是否补联赛映射、球队别名或调整批次。它不需要 Codex 在旁边实时监控。

## 目标

- 新增 dry-run 诊断命令，只请求 OddsPapi `fixtures`，不拉取 `historical-odds`。
- 不写入 `odds_source_matches`、`historical_odds_snapshots`，避免污染正在回填的数据状态。
- 对每场候选比赛输出所有 OddsPapi fixture 候选及相似度分数，方便处理“同一时间多场比赛”误判问题。
- 报告落盘到日志目录，脚本结束后人工查看即可。

## 命令

```powershell
C:\Python312\python.exe src\icewine_cli.py odds-source oddspapi-diagnose-fixtures `
  --season 2025 `
  --max-matches 50 `
  --request-budget 100 `
  --timeout-seconds 20 `
  --log-dir logs/odds-diagnostics `
  --league-ids 135,140 `
  --from-date 2026-01-15 `
  --confidence-threshold 0.75
```

也可以用 `Start-Process` 或任务计划程序后台运行。该命令本身会完整跑完并写出报告，不要求交互式确认。

## 匹配规则

诊断服务复用当前工程已有的 OddsPapi 同步基础设施：

- 使用 `API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS` 将 API-Football 联赛 id 映射到 OddsPapi tournament id。
- 使用当前 `OddsPapiSyncClient.fetch_fixtures()` 的 UTC 时间窗口：本地比赛开球时间转换到 UTC 后前后各 2 小时。
- 使用现有外部别名表中 `source_name=oddspapi`、`entity_type=team` 的球队别名。
- 每个返回 fixture 都计算主队相似度、客队相似度和 `confidence=min(home_similarity, away_similarity)`。
- 候选按 `confidence` 降序、时间差升序排序。
- `confidence >= --confidence-threshold` 记为 `matched`，否则记为 `manual_review`。

## 输出文件

每次运行创建一个独立目录：

```text
logs/odds-diagnostics/<run_id>/
```

`run_id` 使用北京时间，并包含微秒，避免多个诊断任务同一秒启动时互相覆盖报告。

目录内包含：

- `run.json`：本次运行汇总信息。
- `matches.jsonl`：每场比赛一行 JSON，包含候选 fixture 明细和相似度。
- `manual_review.csv`：只列出非 `matched` 的比赛，便于人工筛选。
- `summary.md`：人读摘要。

## 状态含义

- `matched`：最佳候选达到相似度阈值。注意它仍然是 dry-run 结果，不会写入数据库映射表。
- `manual_review`：OddsPapi 有候选 fixture，但球队名相似度不足，优先检查球队别名或比赛归属。
- `no_candidate`：UTC 时间窗口内没有返回 fixture，优先检查联赛映射、比赛状态、时间窗口和 OddsPapi 覆盖。
- `missing_tournament_mapping`：API-Football 联赛 id 尚未配置 OddsPapi tournament id。
- `api_error`：请求 OddsPapi fixture 阶段发生异常或预算耗尽。

## 使用建议

先按单联赛、小批量运行，例如 `--league-ids 140 --max-matches 20`。确认报告结构和错误类型后，再扩大到多个联赛。多个诊断任务不要并行压测 OddsPapi，尤其是 fixture 接口；如果需要连续诊断多个联赛，应顺序执行并保留短暂间隔，避免 `429` 限流影响判断。

如果 `manual_review.csv` 中大量出现相似度为 0 的候选，优先补 `aliases add --source-name oddspapi --entity-type team ...`。如果大量出现 `no_candidate`，优先核对 tournament id、比赛是否属于附加赛、OddsPapi 是否覆盖该赛事。

诊断联赛可用性时优先选择常规赛中段样本，例如 3 月到 4 月，或该联赛赛季相对中间的比赛。赛季末样本可能混入升级附加赛、降级附加赛、争冠组、保级组或其他特殊归属；API-Football 与 OddsPapi 对这些比赛的 tournament 归属可能不同。因此，末轮或附加赛附近的 `404`、`no_candidate` 不能直接视为整个联赛不可回填，必须再用常规赛中段样本复测。

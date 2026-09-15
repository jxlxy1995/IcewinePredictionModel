# 2026-09-15 纸面推荐快照半月回顾提示词

请继续 IcewinePredictionModel 项目的纸面推荐快照回顾工作。

本次是原定 2026-09-15 执行的 9 月上半月轻量回顾，应在 2026-09-15 或之后执行。开始前请阅读：

- `Agent.md`
- `memory.md`
- `docs/交接/20260901-paper-snapshot-monthly-review.md`
- `docs/交接/20260816-paper-snapshot-half-month-review.md`
- `docs/superpowers/specs/2026-08-04-paper-snapshot-review-all-source-design.md`
- `docs/superpowers/handoffs/2026-06-23-paper-snapshot-real-data-handoff.md`

## 数据与安全约束

- 必须使用真实本地数据，不使用 mock，不只做代码推断。
- Python 必须使用 `C:\ProgramData\anaconda3\python.exe`，设置 `$env:PYTHONPATH='src'` 和 `$env:PYTHONIOENCODING='utf-8'`。
- 主数据源是本地 `local_data/icewine_prediction.sqlite3`；SQLite 可以使用 `mode=ro` 只读连接。
- 优先查询 `/api/paper-snapshot-review`，显式查询 `snapshot_source=all`、`automation`、`manual_record`、`historical_backfill`，并检查是否存在其他来源。
- All 必须按 `group_key` 去重，选择优先级为：`automation > manual_record > 其他来源 > historical_backfill`；同一来源内再按较新的 `created_at`、较大的 `id` 处理并列。
- 核对 API 的 `input_group_count`、`selected_group_count`、`excluded_group_count` 和 `groups.by_snapshot_source`。如有排除记录，列出重复 `group_key` 的候选来源、各快照 ID 和最终选择原因。
- 只有在确认来源间无重复后，CLI `records snapshot-report` 不带 `--source` 的结果才可作为 All 合并参考；同时用 `--source automation` 交叉核对主源。
- 禁止执行写入式 `historical_backfill`，禁止修改代码、策略、权重、模型、手数、stake cap、联赛准入、生产逻辑或数据库。

## 回顾窗口与时间口径

- 完整上半月：`2026-09-01T00:00:00` 至 `2026-09-14T23:59:59`
- 第一段：`2026-09-01T00:00:00` 至 `2026-09-07T23:59:59`
- 第二段：`2026-09-08T00:00:00` 至 `2026-09-14T23:59:59`
- 时间轴按代表记录的 `kickoff_time`，全部按北京时间解释；不要使用快照 `created_at` 作为窗口归属。
- 必须输出完整逐日分布，并单独列出 09-01 至 09-07、09-08 至 09-14。

## 必须回答的问题

1. 9 月上半月 automation 是否转正；第二段相对第一段是恢复、延续回撤，还是样本不足不能判断。与 8 月基线对照时，使用真实本次数据，不预设结论：8 月 automation 全月为 772 组、weighted profit `+11.204`、weighted ROI `+1.56%`；8 月前半为 `-14.252/-4.13%`，后半为 `+25.456/+6.82%`。
2. 亏损是否集中在少数日期。先根据逐日 weighted profit 找出最大负日、负日数量和连续负窗口，再说明是否转为连续、广泛亏损；不要把 8 月的 08-08 至 08-10 直接套用到 9 月。
3. 大小球与亚盘的差异、大小球 over/under 差异、亚盘客队与主队方向差异是否持续；同时报告完整窗口和两段结果。
4. 置信度 `60-74`、`75-89`、`85-89`、`90-94` 的样本和收益是否改善，收益是否仍非单调；对 90-94 明确标注样本量。
5. 建议手数 `0.75`、`1.00`、`1.25`、`1.50`、`2.00` 的表现。必须同时报告组数和冻结手数，不能被少量 2.00 手误导。
6. 盘口桶 `low_<=2.25`、`mid_2.50`、`mid_2.75`、`high_>=3.00`、亚盘 `pickem` 的表现。
7. `total_goals_hgb` 是否继续偏弱；`total_goals_distribution_hgb` 是否保持改善。区分 family 互斥统计与“包含该 family”的交集统计。
8. 单信号与双信号差距；跨 family 组合的数量、样本、冻结手数、weighted profit 和 ROI。
9. 瑞典超甲、芬超、巴西甲的负贡献是否延续；冰岛超、中超、美职联、韩K2联的改善是否延续；芬甲按小样本判断。每个联赛至少列全月上半段、第一段、第二段的组数、weighted profit 和 ROI。
10. pending、来源重复、异常来源、版本、时间边界、代表记录与当前比赛 kickoff 漂移及整体数据质量。

## 必须执行的只读交集/差集诊断

针对本期真实数据，至少对以下维度执行只读诊断：

- `total_goals_hgb`
- `mid_2.75`
- `suggested_stake_units=1.50`
- 单信号（`signal_record_ids_json` 只有 1 个）
- 由逐日结果识别出的本期最大集中负日/连续负窗口

要求：

- 报告每个单项的组数、冻结手数、weighted profit 和 weighted ROI。
- 报告二项及以上交集的去重结果；至少列出关键二项交集，并报告“至少两项交集”的总组数、冻结手数、weighted profit 和 ROI。
- 排除集中负日/窗口后，重新报告至少两项交集的组数、冻结手数、weighted profit 和 ROI。
- 交集按组只计算一次，明确说明不能把重叠维度的亏损简单相加。若 `total_goals_hgb` 同时出现在 family 互斥表和包含式交集中，解释两者组数差异。

## 收益和质量口径

- Flat ROI 必须同时报告：包含 0 手的分母，以及剔除 0 手后的 Flat ROI。
- Weighted ROI 始终使用冻结的 `suggested_stake_units` 和冻结手数；不要用当前策略重新计算建议手数。
- 检查 `snapshot/group_key` 重复、代表记录、代表记录是否在 signal IDs 中、signal JSON/strategy IDs/family JSON 是否可解析、盘口桶、代表赔率、负手数、结算缺失收益、过期 pending、版本、来源和时间边界。
- 检查代表记录 kickoff 与当前 `matches.kickoff_time` 的漂移：列出快照 ID、group key、旧/新北京时间、偏移分钟数，并说明是否跨日期或跨窗口。
- 检查代表记录当前状态、结算结果、比赛状态和比分是否一致；结构性异常与统计表现异常分开描述。
- 如果快照创建时 `status=pending` 但代表记录当前已 settled，按现有服务口径说明这是冻结状态与当前结算状态的差异，不要误报为 pending 堆积。

## 输出与落盘

请先给出查询口径、真实 API/CLI 结果和关键表格，再给出结论。表格至少包含：

- All/automation/manual_record/historical_backfill 来源总览和去重计数；
- 完整窗口、第一段、第二段、两段周窗口；
- automation 完整逐日分布；
- 市场/方向、置信度、手数、盘口桶、family/信号数量、重点联赛；
- 交集/差集诊断和数据质量清单。

结论只提出后续只读诊断或研究建议，不直接调整生产逻辑。最终写入：

`docs/交接/YYYYMMDD-paper-snapshot-half-month-review.md`

其中 `YYYYMMDD` 使用实际执行日期；只写真实数据、口径、诊断和观察结论。

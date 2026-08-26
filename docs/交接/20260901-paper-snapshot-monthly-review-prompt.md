# 2026-09-01 纸面推荐快照正式月度回顾提示词

以下内容建议在 2026-09-01 或之后交给 Codex 使用，以确保覆盖完整的
2026 年 8 月自然月。

```text
请继续 IcewinePredictionModel 项目的纸面推荐快照回顾工作。

当前回顾节奏：
- 每月 1 号做正式月度回顾。
- 每月 15 号做轻量半月回顾。
- 2026-08-03 已补做原定 2026-08-01 的 7 月正式月度回顾。
- 2026-08-16 已补做原定 2026-08-15 的 8 月轻量半月回顾。
- 本次是原定 2026-09-01 的 8 月正式月度回顾。
- 为覆盖完整 8 月自然月，本次应在 2026-09-01 或之后执行。

开始前请先阅读：
1. Agent.md
2. memory.md
3. docs/superpowers/handoffs/2026-06-23-paper-snapshot-real-data-handoff.md
4. docs/superpowers/specs/2026-06-22-paper-recommendation-group-snapshots-design.md
5. docs/superpowers/plans/2026-06-22-paper-recommendation-group-snapshots.md
6. docs/交接/20260716-paper-snapshot-half-month-review.md
7. docs/交接/20260803-paper-snapshot-monthly-review.md
8. docs/superpowers/specs/2026-08-04-paper-snapshot-review-all-source-design.md
9. docs/交接/20260816-paper-snapshot-half-month-review.md

请使用真实本地数据，不要只做代码推断，不要使用 mock 数据。

本次正式月度回顾窗口：
- from_date: 2026-08-01T00:00:00
- to_date: 2026-08-31T23:59:59
- 时间轴按代表纸面记录的比赛 kickoff_time，不按快照 created_at。
- 所有时间按北京时间解释和展示。

请同时输出三个主要时间层次：
1. 完整月度：2026-08-01 至 2026-08-31
2. 前半月：2026-08-01 至 2026-08-15
3. 后半月：2026-08-16 至 2026-08-31

为检查时间集中性，还应：
- 单列 2026-08-01 至 2026-08-07。
- 单列 2026-08-08 至 2026-08-15。
- 按 kickoff 日期输出完整 8 月逐日分布。
- 必要时把 2026-08-16 至 2026-08-31 再按 8 天左右拆分，判断恢复或
  回撤是否只集中于少数日期。
- 特别复查 2026-08-08 至 2026-08-10 的集中回撤之后，后半月是否恢复。

并与以下窗口做简要比较：
- 完整 2026 年 7 月。
- 2026-07-17 至 2026-07-31。
- 2026-08-01 至 2026-08-15。
- 2026-05-01 至 2026-06-24 historical_backfill 历史阶段。
- 比较时必须明确来源性质不同，不要把 historical_backfill 与正常运行
  automation 当成完全同质样本。

快照来源口径：
- 正常使用场景以 automation 为主。
- manual_record 是少量人工补充，必须单独报告。
- historical_backfill 不再作为新运行窗口的默认主口径。
- 不要因为 Web 页面默认选择 historical_backfill，就把空页面当作本月
  无数据。
- 必须检查本窗口所有 snapshot_source，包括 automation、manual_record、
  historical_backfill，以及是否存在其他来源。
- 不要执行写入式 historical_backfill，除非我明确要求。

查询方式：
1. 优先使用 Web API /api/paper-snapshot-review。
2. 分别显式查询：
   - snapshot_source=all
   - snapshot_source=automation
   - snapshot_source=manual_record
   - snapshot_source=historical_backfill
3. All 模式按 group_key 去重。检查 API 返回的 deduplication：
   input_group_count、selected_group_count、excluded_group_count。
4. 检查 groups.by_snapshot_source，并与各来源显式查询交叉核对。
5. 如果 All 模式排除了记录，必须查明重复 group_key、涉及来源、各候选
   snapshot ID/created_at，以及最终保留来源。
6. 当前 All 去重优先级为：
   automation > manual_record > 其他来源 > historical_backfill。
   同一优先级内选择较新 created_at，再以较大 ID 作为最终 tie-break。
7. 使用 CLI records snapshot-report 交叉核对总览、来源、市场感知盘口桶、
   market_type + stake_bucket 和 market_type + line_bucket。
8. CLI 不传 --source 时行为没有改成 API All 去重模式。只有确认来源间
   不存在重复后，才可把 CLI 无来源报告作为合并参考。
9. 如需检查交叉重叠、逐日分布和结构质量，可只读查询本地 SQLite；必须
   使用只读连接，不得写库。

请分别查看：
- 总览
- snapshot_source
- market_type
- market_side
- confidence_bucket
- stake_bucket
- stake_cap_reason
- market_type + stake_bucket
- market_type + line_bucket
- signal_family_combo
- signal_count
- league
- 高置信亏损样本
- pending 样本
- 按 kickoff 日期的每日分布

已知历史阶段基准：
- 2026-05-01 至 2026-06-24 historical_backfill：
  - group_count: 850
  - settled_groups: 850
  - pending_groups: 0
  - flat_roi: +25.71%
  - weighted_roi: +27.50%
- 该历史窗口的 API All 不是上述基准：All 输入 857、选择 855、排除 2。
  两个重叠 group_key 为：
  - 14280:total_goals:under
  - 14281:total_goals:over
  两者均同时存在 automation 与 historical_backfill，All 正确保留
  automation。因此历史比较必须继续使用显式 historical_backfill=850，
  不要用历史 All 替代。

已知完整 2026 年 7 月基准：
- automation：
  - group_count: 282
  - settled_groups: 282
  - pending_groups: 0
  - flat_roi: -9.25%
  - weighted_profit: -22.125
  - weighted_roi: -8.16%
- manual_record：
  - group_count: 6
  - settled_groups: 6
  - pending_groups: 0
  - flat_roi: +78.33%
  - weighted_profit: +5.485
  - weighted_roi: +87.76%
- historical_backfill: 0 组
- All/实际来源合计：
  - group_count: 288
  - settled_groups: 288
  - pending_groups: 0
  - flat_roi: -7.43%
  - weighted_profit: -16.640
  - weighted_roi: -6.00%
  - 当时来源间没有重复 group_key。

已知 2026-07-17 至 2026-07-31 基准：
- automation：182 组，flat ROI -4.96%，weighted profit -7.636，
  weighted ROI -4.43%。
- manual_record：4 组，flat ROI +67.00%，weighted profit +2.700，
  weighted ROI +77.14%。
- All/实际来源合计：186 组，flat ROI -3.41%，weighted profit -4.936，
  weighted ROI -2.81%。
- historical_backfill：0 组。

已知 2026-08-01 至 2026-08-15 基准：
- automation：
  - group_count: 362
  - settled_groups: 362
  - pending_groups: 0
  - flat_profit: +3.780
  - flat_roi: +1.04%
  - weighted_profit: -14.252
  - weighted_roi: -4.13%
- manual_record：
  - group_count: 14
  - settled_groups: 14
  - pending_groups: 0
  - flat_profit: +3.705
  - flat_roi: +26.46%
  - weighted_profit: +0.248
  - weighted_roi: +1.84%
- historical_backfill: 0 组
- 其他来源: 0 组
- All：
  - group_count: 376
  - settled_groups: 376
  - pending_groups: 0
  - flat_profit: +7.485
  - flat_roi: +1.99%
  - weighted_profit: -14.004
  - weighted_roi: -3.90%
  - deduplication: 376/376/0

8 月上半月分段基准：
- 08-01 至 08-07 automation：147 组，weighted profit +4.318，
  weighted ROI +3.07%。
- 08-08 至 08-15 automation：215 组，weighted profit -18.570，
  weighted ROI -9.07%。
- 08-08 至 08-10 automation：weighted profit -17.558，相当于第二段
  净亏的 94.6%；08-08 和 08-09 合计 -15.625。
- 08-15 automation：64 组，weighted profit +0.120，weighted ROI
  +0.22%，接近打平。

8 月上半月主要结论：
- automation 完整半月 weighted ROI -4.13%，较完整 7 月改善，但没有
  转正；与 7 月后半月 -4.43% 接近，仍处于负收益平台。
- 第一段转正、第二段明显转负，两段不一致；亏损再次集中于少数日期。
- 大小球 214 组、weighted profit -10.751、ROI -7.51%，弱于亚盘。
- 亚盘客队方向 114 组、weighted profit +9.701、ROI +6.41%；亚盘主队
  方向 34 组、weighted profit -13.202、ROI -26.01%，分化明显。
- 置信度收益仍不单调：60-74 为 115 组、weighted profit +4.082、ROI
  +3.65%；75-89 为 127 组、weighted profit -17.014、ROI -8.91%。
- 85-89 为 34 组、weighted profit -5.022、ROI -9.75%；第二段为
  -14.32%。
- 90-94 为 5 组、weighted profit -2.485、ROI -29.24%；不再全部亏损，
  但 07-17 至 08-15 连续两个新窗口合计 10 组、weighted profit
  -10.985、ROI -61.03%。
- 0.75 手 50 组、ROI +2.32%；1.00 手 28 组、ROI +18.71%；1.25 手
  37 组、ROI -4.38%。7 月三档同步亏损的情况没有继续。
- 1.50 手 129 组、weighted profit -16.499、ROI -8.53%；7 月后半月
  +9.70% 的恢复没有延续。第二段大小球 1.50 手 19 组、weighted profit
  -9.855、ROI -34.58%。
- 2.00 手只有 3 组，weighted profit -3.000，不足以据此调整 stake cap。
- low_<=2.25 为 35 组、weighted profit -4.929、ROI -18.78%，延续
  7 月稳定负收益。
- mid_2.75 为 33 组、weighted profit -12.497、ROI -25.25%；第二段
  -41.39%，7 月后半月的恢复没有延续。
- high_>=3.00 为 77 组、weighted profit +5.625、ROI +10.71%，两段
  均为正，属于需要验证延续性的改善项。
- pickem 为 7 组、weighted profit +6.810、ROI +69.85%，样本仍小。
- mid_2.50 为 69 组；其中 39 个 0 手组。30 个非 0 手组 flat ROI 与
  weighted ROI 均为 +7.00%，主要改善来自第二段，但样本仍不足以认定
  稳定盈利。
- total_goals_hgb 为 67 组、weighted profit -15.426、ROI -20.92%；
  第二段 -32.69%，没有继续改善。
- total_goals_distribution_hgb 为 146 组、weighted profit +6.675、ROI
  +9.89%，两段均为正，暂时摆脱 7 月约 -7% 的弱势。
- 单信号 284 组、weighted profit -18.997、ROI -8.24%；双信号 78 组、
  weighted profit +4.745、ROI +4.14%。双信号两段均为正，差距继续存在。
- 出现 1 个跨 family 组合：
  total_goals_distribution_hgb+total_goals_hgb，weighted profit -2.000。
  单个样本不能评价跨 family 组合质量。
- 重点联赛中，冰岛超、中超、韩K2联转正，美职联接近打平；7 月四项同步
  负贡献没有延续。
- 芬甲仅 2 组为正，样本不足；芬超 12 组、weighted profit -3.305；
  巴西甲 7 组、-1.430；瑞典超甲 9 组、-8.219。后三项此前恢复或正贡献
  没有延续，瑞典超甲是上半月最大联赛拖累。
- automation 含 0 手 Flat ROI +1.04%；47 个 0 手组 flat profit
  +9.180；剔除 0 手后 Flat ROI -1.71%。Weighted ROI 始终按冻结手数，
  不受 0 手剔除影响。
- 上半月无 pending、来源重复、无效赔率、负手数、缺失收益、版本混入、
  signal JSON/IDs/group 语义异常或其他会改变统计的结构问题。
- 发现 4 个快照、2 场比赛的代表记录 kickoff 与当前 matches 表时间轻微
  不一致：
  - 快照 1306、1307：挪甲诺霍斯对斯塔贝克，23:00 对当前 23:15。
  - 快照 1329、1330：墨西超托卢卡对内卡萨，09:05 对当前 09:10。
  两场均未跨日期或窗口，API/CLI 按代表记录 kickoff 的既定统计不受影响。
- 8 月半月回顾决定保持全部策略、权重、手数、stake cap、联赛准入和
  生产逻辑不变。

本次正式月度回顾重点回答：
1. 完整 8 月 automation weighted ROI 是否转正或进入健康区间；后半月
   是否从上半月 -4.13% 和 08-08 至 08-10 集中回撤中恢复。
2. 前后半月表现是否一致；完整月亏损是否仍由少数日期造成，还是后半月
   出现连续、广泛亏损。
3. 08-08 至 08-10 之后逐日表现如何；08-15 接近打平是否具有延续性。
4. 大小球是否仍弱于亚盘；亚盘客队方向的正贡献和亚盘主队方向的显著
   负贡献是否继续分化。
5. 60-74、75-89、85-89、90-94 的完整月及后半月表现；置信度收益是否
   恢复基本单调性。
6. 90-94 在 07-17 至 08-15 连续 10 组严重偏弱后是否继续异常；必须逐个
   列出新增 90-94 样本，结合样本量判断。
7. 0.75、1.00 手的上半月转正是否延续；1.25 手是否恢复。
8. 1.50 手是否继续显著拖累，特别区分亚盘和大小球，并检查第二段
   大小球 1.50 手的严重亏损是否延续。
9. 不要被少量 2.00 手盈利或亏损样本误导，不要据此调整 stake cap。
10. low_<=2.25 是否继续稳定亏损；mid_2.75 是否仍为核心拖累；
    high_>=3.00 的正收益是否延续。
11. mid_2.50 必须区分 0 手和非 0 手；pickem 必须结合样本量判断。
12. total_goals_hgb 是否继续异常偏弱；total_goals_distribution_hgb 的正
    收益是否能延续，还是短期反转。
13. 单信号与双信号差距是否持续；说明跨 family 组合的数量、组成、样本
    和收益，不要把同 family 双信号误称为跨 family。
14. 瑞典超甲、芬超、巴西甲是否继续负贡献；冰岛超、中超、美职联、
    韩K2联的改善是否延续；芬甲必须按样本量判断。
15. pending 是否堆积，是否存在已经应结算但缺失收益的记录。
16. automation 与 manual_record 是否存在重复 group_key；All 合并结果
    是否可信，是否出现新来源。
17. 0 手组对 Flat ROI 的影响：同时给出包含 0 手和剔除 0 手后的 Flat
    结果；Weighted ROI 始终保持冻结建议手数口径。
18. 上半月发现的 4 个 kickoff 漂移快照是否仍是孤立情况；完整月是否新增
    代表记录 kickoff 与当前 matches.kickoff_time 不一致的快照，是否跨越
    日期或月度边界。

只读专项交叉诊断：
- 8 月上半月的主要负标签 `total_goals_hgb`、`mid_2.75`、1.50 手、
  单信号和 08-08 至 08-10 彼此高度可能重叠。不能把各维度 weighted
  profit 相加，当成互相独立的损失。
- 请在只读数据上计算这些标签的交集和差集，至少报告：
  1. 每个标签单独的组数、冻结手数、weighted profit 和 ROI。
  2. 同时命中两个及以上标签的组数、冻结手数、weighted profit 和 ROI。
  3. `total_goals_hgb` 中 mid_2.75 与非 mid_2.75 的表现。
  4. mid_2.75 中 total_goals_hgb 与其他 family 的表现。
  5. 1.50 手中亚盘/大小球、单信号/双信号、不同 family 的表现。
  6. 排除 08-08 至 08-10 后，上述标签及 automation 全局结果是否仍为负。
  7. 后半月新增样本是否重复同一结构。
- 该专项只用于区分独立问题与重复归因，不修改查询服务、策略或数据库。

异常数据检查至少包括：
- snapshot ID 是否重复。
- 同一来源内 group_key 是否重复。
- 不同来源间是否存在相同 group_key。
- All 去重选择结果是否符合来源优先级、created_at 和 ID tie-break。
- representative_record 是否缺失或不属于 signal record。
- line_bucket 是否缺失或与代表记录不一致。
- 代表盘口和赔率是否与代表记录一致。
- 快照代表赔率、代表记录原始赔率和当前赔率是否缺失、非数字或小于等于 1。
- suggested_stake_units 是否为负。
- 已结算记录是否缺少 profit_units。
- 已过合理结算时间但仍为 pending 的比赛。
- 代表记录 kickoff_time 是否确实位于北京时间窗口内。
- 代表记录 kickoff_time 与当前 matches.kickoff_time 是否漂移；列出快照、
  比赛、两个时间、偏移分钟数，并说明是否跨日期或窗口边界。
- snapshot_version 是否混入非 paper_confidence_v1 版本。
- 是否存在未预期的 snapshot_source。
- 快照 signal IDs、signal JSON、策略 key/display name JSON 和 group_key
  语义是否一致。
- 快照行冻结 status 与代表记录当前 status 的差异是否符合既有设计。

决策原则：
- 如果样本不足，只给观察建议，不强行下结论。
- 不修改策略参数、评分权重、模型、联赛准入或生产逻辑。
- 默认继续保持所有策略和手数不变。
- 不因单个短窗口提高 stake cap，也不因少数亏损样本删除策略。
- 即使整体仍为负，也先判断亏损是否集中于时间、市场、family、线位、
  手数桶或联赛。
- 必须通过交集/差集避免重复归因，不能把相互重叠分组的 weighted profit
  简单相加。
- 只有同一异常在完整 8 月新增样本中持续，并且样本量、收益幅度、时间
  分布和结构一致性都明显增强时，才建议安排后续策略调整研究。
- 即使证据增强，本次也只允许提出后续只读诊断或研究建议，不直接修改
  策略、权重、手数、stake cap、联赛准入或生产逻辑。
- 本次只做真实数据回顾和文档化结论，不执行数据回填，不修改代码或策略。

请最终给出：
1. 本次完整月度窗口、北京时间口径、查询方式及 All 去重规则。
2. automation、manual_record、historical_backfill、其他来源及 All 的组数、
   已结算、pending、flat/weighted profit、flat/weighted ROI。
3. 完整 8 月、08-01 至 08-15、08-16 至 08-31 三个时间层对比，并补充
   08-01 至 08-07、08-08 至 08-15 和完整逐日分布。
4. 与完整 7 月、7 月后半月、8 月上半月及历史回填阶段基准的简要比较，
   明确来源差异。
5. 主要正贡献与负贡献分组，同时给出样本量、冻结手数和 weighted profit，
   不能只报 ROI。
6. 高置信度、各手数桶、特定盘口线位、signal family、信号数和重点联赛
   结论。
7. `total_goals_hgb`、`mid_2.75`、1.50 手、单信号和集中回撤日期的交集/
   差集诊断，明确哪些是重复归因，哪些在排除交集后仍独立偏弱。
8. 包含 0 手与剔除 0 手后的 Flat ROI；Weighted ROI 保持冻结建议手数
   口径。
9. pending 和完整数据质量检查结果，包括 kickoff 漂移复核。
10. 结构性数据异常与统计表现异常分开说明。
11. 是否建议调整策略、权重或手数；默认结论应为不调整，除非证据非常
    明确。即便建议研究调整，也不要在本次执行修改。
12. 下一次 2026-09-15 左右轻量半月回顾应重点追踪的项目。

请将最终结论写入：
docs/交接/YYYYMMDD-paper-snapshot-monthly-review.md

其中 YYYYMMDD 使用实际执行日期。文档只记录真实数据、查询口径、交叉
诊断、结论和后续观察项，不修改代码、策略或数据库。
```

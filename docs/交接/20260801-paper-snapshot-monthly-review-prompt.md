# 2026-08-01 纸面推荐快照正式月度回顾提示词

以下内容可以在 2026-08-01 直接交给 Codex 使用。

```text
请继续 IcewinePredictionModel 项目的纸面推荐快照回顾工作。

当前回顾节奏：
- 每月 1 号做正式月度回顾。
- 每月 15 号做轻量半月回顾。
- 2026-06-24 已完成 2026-05-01 至 2026-06-24 的阶段回顾，因此
  2026-07-01 的正式月度回顾已跳过。
- 2026-07-16 已补做原定 2026-07-15 的半月轻量回顾。
- 本次是 2026-08-01 正式月度回顾。

开始前请先阅读：
1. Agent.md
2. memory.md
3. docs/superpowers/handoffs/2026-06-23-paper-snapshot-real-data-handoff.md
4. docs/superpowers/specs/2026-06-22-paper-recommendation-group-snapshots-design.md
5. docs/superpowers/plans/2026-06-22-paper-recommendation-group-snapshots.md
6. docs/交接/20260716-paper-snapshot-half-month-review.md

请使用真实本地数据，不要只做代码推断，不要使用 mock 数据。

本次正式月度回顾窗口：
- from_date: 2026-07-01T00:00:00
- to_date: 2026-07-31T23:59:59
- 时间轴按比赛 kickoff_time，不按快照 created_at。
- 所有时间按北京时间解释和展示。

快照来源口径：
- 后续正常使用场景以 automation 为主。
- 少量人工操作使用 manual_record，作为补充来源单独报告。
- historical_backfill 主要用于历史回填阶段，不再作为新运行窗口的默认主口径。
- 不要因为默认 Web 页面使用 historical_backfill，就把空页面当作本月无数据。
- 必须检查本窗口全部 snapshot_source 分布，至少包括
  historical_backfill / automation / manual_record，以及是否存在其他来源。
- 分别报告 automation、manual_record 和 historical_backfill。
- 检查不同来源是否存在相同 group_key 或其他重复计数风险；确认没有重复后，
  再提供所有实际来源的合并参考结果。
- 不要为了填充 historical_backfill 页面而执行写入式回填，除非我明确要求。

查询方式：
1. 优先使用 Web API /api/paper-snapshot-review。
2. 使用 CLI records snapshot-report 交叉核对总览、source 和市场感知盘口桶。
3. API 查询 automation 时必须显式传入 snapshot_source=automation；
   manual_record 和 historical_backfill 同理。
4. 如需合并口径，可使用 CLI 不传 --source 的报告，但必须先检查来源间重复。

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

请同时输出三个时间层次：
1. 完整月度：2026-07-01 至 2026-07-31
2. 前半月：2026-07-01 至 2026-07-16
3. 后半月：2026-07-17 至 2026-07-31

必要时额外检查 2026-07-09 至 2026-07-12，判断上次发现的集中回撤是否
延续、恢复或只是短期波动。

已知历史阶段基准：
- 2026-05-01 至 2026-06-24 historical_backfill：
  - group_count: 850
  - settled_groups: 850
  - pending_groups: 0
  - flat_roi: 0.2571
  - weighted_roi: 0.2750

已知 2026-07-01 至 2026-07-16 半月基准：
- automation：
  - group_count: 100
  - settled_groups: 100
  - pending_groups: 0
  - flat_roi: -0.1707
  - weighted_roi: -0.1464
- manual_record：
  - group_count: 2
  - settled_groups: 2
  - pending_groups: 0
  - flat_roi: 1.0100
  - weighted_roi: 1.0127
- 实际来源合计：
  - group_count: 102
  - settled_groups: 102
  - pending_groups: 0
  - flat_roi: -0.1475
  - weighted_roi: -0.1150
- historical_backfill: 0 组

上次半月重点异常与观察项：
- automation weighted ROI -14.64%，整体不健康。
- 亏损主要集中在 2026-07-09 至 2026-07-12，该段 weighted ROI -26.88%。
- 1.50 手组 32 组，weighted ROI -31.67%，是最大拖累。
- 85-89 置信度 10 组，weighted ROI -50.20%。
- 90-94 置信度只有 4 组但 weighted ROI +57.87%，置信度收益不单调。
- total_goals_hgb 23 组，weighted ROI -26.01%。
- 大小球 low_<=2.25 weighted ROI -25.54%。
- 大小球 mid_2.75 weighted ROI -26.41%。
- 亚盘 pickem 只有 3 组，weighted ROI +21.84%，没有异常亏损。
- 大小球 mid_2.50 weighted ROI +20.40%，但 flat ROI 为负，需要继续区分
  0 手和实际建议手数口径。
- 单信号组 78 组，weighted ROI -20.76%；双信号组 22 组，weighted ROI
  -2.93%。
- 冰岛超上阶段和本次均为负，但两期合计样本仍很小。
- 上次 pending 为 0，数据完整性检查未发现重复、缺失赔率、缺失收益或
  无效手数。

本次重点回答：
1. 完整 7 月和后半月 automation weighted ROI 是否恢复到健康区间。
2. 7 月 9 至 12 日是否只是集中回撤，还是后续仍持续亏损。
3. 75-89，特别是 85-89 高置信度组是否继续异常亏损；检查置信度收益
   是否具有基本单调性。
4. 1.50 手组是否继续显著拖累；不要被少量 2.00 手盈利样本误导。
5. total_goals_hgb、low_<=2.25、mid_2.75 和 high_>=3.00 是否恢复。
6. pickem 和 mid_2.50 是否保持稳定，注意样本量和 0 手影响。
7. 单信号组与双信号组的差距是否持续。
8. 冰岛超、爱甲、芬甲、中超、芬超等负贡献联赛是否新增了足够样本，
   不要对小样本强行下结论。
9. 世界杯、韩K联、瑞典超等正贡献是否具有延续性，还是赛事结构造成的
   短期结果。
10. pending 是否堆积，是否存在应结算但缺失收益的记录。
11. 0 手组对 flat ROI 的影响：同时给出包含 0 手和剔除 0 手后的 flat
    结果；weighted ROI 保持冻结建议手数口径。
12. automation 与 manual_record 是否有重复 group key，合并结果是否可信。

异常数据检查至少包括：
- snapshot ID 和 group_key 是否重复。
- 来源间是否重复计数。
- representative_record 是否缺失。
- line_bucket 是否缺失。
- 赔率是否无效。
- suggested_stake_units 是否为负。
- 已结算记录是否缺少 profit_units。
- kickoff_time 是否确实落在本次窗口。
- snapshot_version 是否混入非 paper_confidence_v1 版本。

决策原则：
- 如果样本量不足，不要强行下结论，只给观察建议。
- 不要修改策略参数、权重、模型或生产逻辑，除非我明确要求。
- 默认倾向仍是不调整。
- 即使完整 7 月仍为负，也先判断亏损是否集中于时间、联赛、family、线位
  或手数桶，再考虑是否需要后续专项诊断。
- 不要仅凭少量高收益组提高 stake cap，也不要仅凭一个短窗口整体删除策略。

请最终给出：
1. 本次正式月度回顾窗口、数据源和去重口径。
2. automation、manual_record、historical_backfill 及实际来源合计的组数、
   已结算、pending、flat ROI、weighted ROI。
3. 完整月度、前半月、后半月的对比。
4. 与 2026-05-01 至 2026-06-24 阶段基准及 2026-07-01 至 2026-07-16
   半月基准的简要对比，并明确来源差异。
5. 主要正贡献和负贡献分组。
6. 高置信度、高建议手数、特定盘口线位、signal family 和联赛的观察结论。
7. 0 手组、pending 和数据完整性检查结果。
8. 是否出现结构性数据异常或统计表现异常，两者分开说明。
9. 是否建议调整策略或权重；默认不调整，除非证据非常明确。
10. 下一次 2026-08-15 轻量半月回顾应重点追踪什么。

请只做真实数据回顾和文档化结论，不要修改代码或策略。
```


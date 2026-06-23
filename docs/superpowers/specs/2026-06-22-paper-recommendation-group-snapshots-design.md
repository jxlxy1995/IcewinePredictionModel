# 纸面推荐组快照与真实运行复盘基建设计

## 背景

纸面推荐链路已经从人工记录推进到自动化任务，并且用户已经连续约两个月按纸面推荐记录做小额实盘参与。当前 `paper_recommendation_records` 虽然仍叫“纸面记录”，但它已经承担了当前真实运行跟踪的主要职责。

现有 Web 纸面推荐页和自动化 Bark 推送会基于 `paper_recommendation_records` 动态调用 `build_paper_confidence_workspace(...)`，把同一场比赛、同一盘口类型、同一方向的多条策略记录聚合成一个推荐组，再计算 `confidence_score` 和 `suggested_stake_units`。这些聚合结果目前不是稳定落库事实，而是当前代码版本生成的视图。

这带来一个复盘风险：如果后续修改 confidence 评分、手数映射、代表记录选择或 stake cap 规则，历史页面重新打开时会被当前逻辑重新解释，无法准确还原当时 Bark/Web 给出的执行建议。

本设计新增推荐组快照表，保存当时系统给出的聚合推荐组判断，为后续真实运行复盘、策略评估、手数校准和页面升级打基础。

## 目标

- 新增 `paper_recommendation_group_snapshots` 表，固化推荐组级别的当时评分和建议手数。
- 保持推荐组聚合规则与现有 Web/Bark 一致：同一场比赛、同一盘口类型、同一方向聚合为一条推荐组。
- 手动批量记录和自动化任务批量记录后自动生成推荐组快照。
- 自动化 Bark 推送优先复用刚生成的快照对应推荐组，保证推送内容与落库快照一致。
- 提供历史 backfill 能力，用当前评分逻辑为已有纸面记录补快照，但明确标记为回填数据。
- 提供首版 CLI 复盘报告，基于快照而不是动态重算的 confidence workspace 统计收益。
- 文档明确：当前不迁移旧 `recommendation_records`；`paper_recommendation_records` 链路是当前实际小额参与跟踪的主链路。

## 非目标

- 本轮不迁移旧 `recommendation_records` 数据。
- 本轮不重建统一正式推荐记录体系。
- 本轮不做纸面推荐页的本周、上周、本月、上月收益与 ROI 看板。
- 本轮不强制把纸面推荐页历史推荐组展示改成只读快照。
- 本轮不直接根据两个月样本调整策略准入、confidence score 或 stake cap。
- 本轮不保存用户真实资金流水、真实下注金额或外部平台订单信息。

## 方案选择

### 方案 A：直接给纸面记录表加字段

给每条 `paper_recommendation_records` 加 `confidence_score_snapshot`、`suggested_stake_units_snapshot` 等字段。实现简单，但语义不准确，因为 confidence 和建议手数属于聚合推荐组，不属于单条策略记录。同一推荐组可能包含多条策略记录，把组级评分重复写到每条记录上会制造歧义。

### 方案 B：新增推荐组快照表

新增 `paper_recommendation_group_snapshots`，保存同一推荐组的信号组成、代表记录、当时评分、建议手数、版本和来源。它把 `paper_recommendation_records` 作为事实源头，把推荐组作为可执行建议快照。

这是本轮推荐方案。

### 方案 C：重建正式推荐记录体系

新建统一正式推荐记录体系，同时整合旧 `recommendation_records` 与当前纸面链路。架构更彻底，但范围过大，会影响已稳定运行的纸面自动化流程。本轮不采用。

## 数据模型

新增表：`paper_recommendation_group_snapshots`

推荐字段：

- `id`
- `created_at`
- `snapshot_source`
- `snapshot_version`
- `group_key`
- `match_id`
- `market_type`
- `side`
- `representative_record_id`
- `signal_record_ids_json`
- `triggered_strategy_keys_json`
- `triggered_strategy_display_names_json`
- `signal_families_json`
- `confidence_score`
- `suggested_stake_units`
- `stake_cap_reason`
- `recommendation_text`
- `representative_market_line`
- `representative_odds`
- `line_bucket`
- `status`
- `settlement_result`
- `flat_profit_units`
- `weighted_profit_units`
- `is_backfilled`
- `source_record_created_at_min`
- `source_record_created_at_max`

字段含义：

- `snapshot_source` 区分快照来源，例如 `manual_record`、`automation`、`historical_backfill`。
- `snapshot_version` 表示评分口径版本，首版可为 `paper_confidence_v1`。
- `group_key` 使用当前推荐组规则生成，例如 `match_id:market_type:side`。
- `signal_record_ids_json` 保存组成该推荐组的纸面记录 ID 列表。
- `representative_record_id` 保存当时 workspace 选择的代表记录。
- `confidence_score` 和 `suggested_stake_units` 是本表最重要的冻结字段。
- `line_bucket` 保存代表推荐组当时使用的盘口桶，后续复盘必须优先结合 `market_type` 解读。
- `is_backfilled` 标记该快照是否由历史回填生成。
- `source_record_created_at_min/max` 用于回填时说明这组信号原始形成时间范围。

可以适度冗余代表盘口、赔率、推荐文本、策略列表和 family 列表。比赛名、球队名、联赛名、最终比分等仍优先通过 `paper_recommendation_records`、`matches` 及相关表读取，避免新表变成第二套完整记录表。

## 聚合规则

推荐组规则必须与当前 Web/Bark confidence workspace 保持一致：

```text
match_id + market_type + side
```

即同一场比赛、同一盘口类型、同一方向聚合为一条推荐组。亚盘和大小球不能混在一起；同一盘口类型的不同方向也不能混在一起。

快照服务不重新定义评分规则，而是复用现有 `build_paper_confidence_workspace(...)` 和 `PaperConfidenceGroup`。如果未来评分规则升级，应通过新的 `snapshot_version` 并存保留，而不是覆盖旧快照。

## 生成时机

### 手动批量记录

Web 纸面推荐页批量记录候选成功后，收集本次新建记录影响到的 `(match_id, market_type, side)` 组合，只为这些推荐组生成快照。

不需要对全部历史记录重算。

### 自动化任务

自动化任务批量创建纸面记录后：

1. 收集新建记录影响到的推荐组。
2. 生成推荐组快照。
3. Bark 推送优先使用刚生成快照对应的推荐组数据。
4. 自动化任务 `result_payload` 记录新建快照 ID 列表。

由于自动化任务本身是实时计算并实时推送，短期显示内容与当前逻辑几乎一致。新增快照的价值在于把当时推送依据稳定保存下来。

### 历史回填

提供显式 backfill 能力，用当前评分逻辑为已有纸面记录补推荐组快照。

回填约束：

- `snapshot_source = "historical_backfill"`
- `is_backfilled = true`
- `created_at` 是回填执行时间。
- `source_record_created_at_min/max` 保存组成该组的原始记录创建时间范围。
- 文档和报告必须明确：回填快照不是当时真实 Web/Bark 评分，只是当前逻辑对历史记录的重放。

## 幂等与版本

同一次触发应幂等，避免重复插入同一组同一版本同一信号集合。

建议幂等键：

```text
snapshot_source + snapshot_version + group_key + signal_record_ids_json
```

如果未来评分逻辑升级，例如 `paper_confidence_v2`，允许同一推荐组同一信号集合生成新版本快照。复盘报告默认使用正式版本，或通过参数指定版本。

## 结算与收益

快照生成时比赛可能尚未完赛，所以 `settlement_result`、`flat_profit_units`、`weighted_profit_units` 不能作为当时必须准确的主事实。

首版采用以下口径：

- 快照冻结 `confidence_score`、`suggested_stake_units`、信号组成、代表记录和版本。
- 复盘报告按快照中的 `suggested_stake_units` 计算 weighted profit。
- flat profit 以代表记录 1 手收益口径计算。
- 不用当前评分器动态重算建议手数。
- 结算状态可在报告阶段通过关联 `paper_recommendation_records` 和比赛结果读取。

这避免在纸面记录结算时额外维护复杂同步逻辑，同时保留真实复盘所需的核心冻结字段。

## CLI

新增历史回填命令：

```powershell
python -m icewine_prediction.cli paper snapshots-backfill `
  --from-date 2026-06-01 `
  --to-date 2026-06-30 `
  --dry-run
```

参数建议：

- `--from-date`
- `--to-date`
- `--source`，默认 `historical_backfill`
- `--version`，默认 `paper_confidence_v1`
- `--dry-run`
- `--overwrite-version`，默认 false

新增复盘报告命令：

```powershell
python -m icewine_prediction.cli paper snapshot-report `
  --from-date 2026-06-01 `
  --to-date 2026-06-30
```

报告首版输出 Markdown 或控制台文本。后续 Web 页面可以复用同一服务。

## 复盘统计口径

复盘基于 `paper_recommendation_group_snapshots`，不基于动态重算的当前 confidence workspace。

首版统计：

- 总览：推荐组数、已结算组数、flat profit、weighted profit、flat ROI、weighted ROI。
- 按 score bucket：`<55`、`55-59`、`60-64`、`65-69`、`70-74`、`75-79`、`80-84`、`85-89`、`90+`。
- 按 stake bucket：`0.50`、`0.75`、`1.00`、`1.25`、`1.50`、`1.75`、`2.00`、`2.50`、`3.00`。
- 按 market type：亚盘、大小球。
- 按 side：home cover、away cover、over、under。
- 按 market type + stake bucket，避免把不同市场下同一建议手数的表现混在一起解释。
- 按 market type + line bucket，避免把大小球 2.5 这类常见盘口和亚盘 2.5 这类深盘混在同一盘口桶里解释。
- 按 strategy family combo。
- 按 snapshot source，区分真实生成与历史回填。

可选输出：

- 按联赛。
- 按单独盘口桶。
- 按具体 strategy key。

这些统计用于判断数据结构和复盘口径是否可靠，不直接作为本轮策略调参依据。

## Web 与 Bark

本轮不做大规模 Web UI 改造。

自动化 Bark：

- 继续保持现有消息格式。
- 自动化任务生成记录后优先复用本次新建快照对应的 group 数据。
- `result_payload` 记录 snapshot ids，便于诊断。

纸面推荐页：

- 本轮不强制把历史推荐组展示替换为快照读取。
- 后续建议：推荐组历史展示优先读取正式快照；缺失快照时 fallback 到动态计算，并明确标记。
- 后续如果要弱化“纸面”命名，可以在页面层升级为“推荐跟踪”或“实盘观察记录”，底层表暂不迁移。

旧正式推荐记录页：

- 本轮不迁移旧 `recommendation_records`。
- 旧正式记录页保持历史兼容。
- 当前纸面链路作为实际运行跟踪主链路继续演进。

## 测试计划

后端测试：

- 初始化数据库会创建 `paper_recommendation_group_snapshots`。
- 从单条纸面记录生成推荐组快照。
- 同一场比赛、同一盘口类型、同一方向的多条记录聚合为一条快照。
- 不同盘口类型或不同方向不会聚合到同一快照。
- 快照保存当时 `confidence_score`、`suggested_stake_units`、`stake_cap_reason`。
- 同一 `snapshot_source + snapshot_version + group_key + signal_record_ids_json` 重复生成不会重复插入。
- 新版本可以为同一组同一信号集合生成新快照。
- 手动批量记录后会生成受影响推荐组快照。
- 自动化任务批量记录后会生成快照，并在 `result_payload` 中包含 snapshot ids。
- 历史 backfill 快照带 `is_backfilled = true` 和 `snapshot_source = historical_backfill`。
- 复盘报告使用快照手数计算 weighted profit，不动态重算手数。
- 复盘报告包含 `market_type + stake bucket` 和 `market_type + line bucket` 组合统计。
- Bark 格式化可以使用快照对应 group 数据，且内容与当前实时计算保持一致。

CLI 测试：

- `snapshots-backfill --dry-run` 不写库，并报告将生成的快照数量。
- `snapshots-backfill` 写入历史回填快照。
- `snapshot-report` 输出总览和分组统计。

验证命令建议：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_paper_recommendation_group_snapshot_service.py tests/test_paper_recommendation_tracking_service.py tests/test_paper_automation_service.py -q
```

如涉及 Web API payload：

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'
C:\ProgramData\anaconda3\python.exe -m pytest tests/test_web_console_api.py -q
```

## 交接说明

- 用户已经约两个月按纸面推荐记录做小额实盘参与。
- 当前工作区不包含用户真实资金流水或完整实盘数据。
- 本轮只建设“当时推荐组可追溯”和“后续复盘可分析”的基础设施。
- 两个月样本可能不足以直接调整策略准入、扩大使用范围或提高 stake cap。
- 后续是否根据真实运行数据调整策略，应由主导开发者结合真实数据、样本量、联赛分布、时间窗口和风险偏好判断。

## 实施顺序

建议后续实现按小步推进：

1. 新增模型与 SQLite schema evolution。
2. 新增推荐组快照服务和幂等生成逻辑。
3. 接入手动批量记录流程。
4. 接入自动化任务流程和 Bark 数据流。
5. 增加历史 backfill CLI。
6. 增加 snapshot-report CLI。
7. 补充交接文档或更新 `memory.md` 中的稳定决策。

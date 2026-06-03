# 纸面推荐鲁棒过滤器接入交接

## 背景

这轮工作围绕纸面推荐候选的赔率时点误差展开。之前的纸面策略主要基于单一赔率口径生成候选；实战中更接近的使用方式是赛前某个时间点拉取 oddspapi 历史赔率快照，并希望候选在 T-25/T-20/T-15/T-10/T-5 这些相邻执行时点上具有一定稳定性。

本轮目标不是重做模型，也不是改变多信号复合评分机制，而是在纸面推荐候选进入记录前增加一层可验证的鲁棒性基建。

## 本轮目标

1. 回测现有 6 个纸面信号在 raw / kept / filtered 三组下的表现。
2. 将 selected robust 规则抽成共享模块，避免报告和推荐链路规则漂移。
3. 纸面推荐优先使用 scheduled 比赛的 oddspapi historical 快照。
4. 未开赛比赛硬过滤不鲁棒候选。
5. 已完赛历史窗口改为模拟真实未开赛操作：不通过鲁棒过滤的候选同样舍弃。
6. API 和前端类型透出 robustness 诊断字段。

## 推荐阅读顺序

1. `src/icewine_prediction/execution_robustness_rules.py`
2. `src/icewine_prediction/baseline_execution_robustness_filter_service.py`
3. `src/icewine_prediction/baseline_execution_robustness_service.py`
4. `src/icewine_prediction/baseline_execution_robustness_grid_service.py`
5. `src/icewine_prediction/baseline_paper_discovery_alignment_service.py`
6. `src/icewine_prediction/paper_recommendation_queue_service.py`
7. `src/icewine_prediction/web_api.py`
8. `web/src/types.ts`
9. `tests/test_baseline_execution_robustness_filter_service.py`
10. `tests/test_baseline_paper_discovery_alignment_service.py`
11. `tests/test_paper_recommendation_queue_service.py`
12. `tests/test_web_console_api.py`

## Selected Robust 规则

| Strategy | Mode | Primary | Seen >= | Min edge | Side | Bucket | Line |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `asian_away_cover_hgb_edge_v1` | filter | T-15 | 5 | 0.0800 | stable | stable | any |
| `asian_away_cover_hgb_bucket_v2` | filter | T-15 | 4 | 0.1200 | stable | stable | any |
| `asian_home_cover_hgb_favorite_bucket_v1` | filter | T-15 | 4 | 0.0800 | stable | stable | any |
| `total_goals_hgb_bucket_v2` | filter | T-15 | 2 | 0.1200 | stable | any | any |
| `total_goals_hgb_low_line_bucket_v3` | filter | T-15 | 3 | 0.1200 | stable | any | any |
| `total_goals_hgb_confirmed_under_mid_275_v1` | filter | T-15 | 3 | 0.1200 | stable | any | any |

`confirmed_under_mid_275` 已改为正常 filter 模式，和其他策略使用同一套舍弃规则。后续如果新口径下表现不佳，再单独重跑并考虑移除该策略。

## 回测结果摘要

本地实际可用 CSV 是 `local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv`，不是代码默认提到的 `20260602-2036` 文件。

报告生成路径：

`docs/模型实验/20260603-baseline-execution-robustness-filter.md`

核心结果：

| Strategy | Raw bets | Raw ROI | Kept bets | Kept ROI | Filtered ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| `asian_away_cover_hgb_edge_v1` | 259 | 0.0558 | 61 | 0.2929 | -0.0173 |
| `asian_away_cover_hgb_bucket_v2` | 159 | 0.0086 | 59 | 0.2170 | -0.1144 |
| `asian_home_cover_hgb_favorite_bucket_v1` | 83 | 0.0911 | 35 | 0.2402 | -0.0177 |
| `total_goals_hgb_bucket_v2` | 81 | 0.0263 | 42 | 0.2231 | -0.1856 |
| `total_goals_hgb_low_line_bucket_v3` | 105 | -0.1160 | 50 | 0.1209 | -0.3314 |
| `total_goals_hgb_confirmed_under_mid_275_v1` | 11 | 0.0119 | 11 | 0.0119 | - |

解读：前 5 个信号的 kept 组明显优于 raw，filtered 组大多为负；这支持将 v0 robust 规则接入未开赛推荐链路。

## 当前推荐链路行为

### Scheduled 与 Finished 统一口径

当比赛有可用 oddspapi historical 快照时，scheduled 未开赛队列和 finished 历史回填使用同一套候选发现与保留逻辑：

1. 构造标准快照组：`T-25 / T-20 / T-15 / T-10 / T-5 / latest`。
2. 每个可用 `match + timepoint` feature row 只跑一次 scorer。
3. scorer 输出继续完整套用 `paper_strategy_registry.py` 中所有策略规则，不为省时间跳过策略判断。
4. 任一标准时点命中策略后，进入 `match_id + strategy_key + market_type + side` 观察组。
5. 对该策略在固定目标时点 `T-25/T-20/T-15/T-10/T-5` 的 score 做 selected robustness rule 评估。
6. 规则通过才返回 `status == "candidate"`。
7. 规则不通过则直接舍弃，不返回 `robustness_filtered` 候选行。

finished 历史回填的目的改为模拟真实未开赛操作，因此不再保留不鲁棒候选。简单诊断字段会统计有多少比赛因为发现了候选但未达到鲁棒过滤级别而被舍弃。

### Unavailable

如果没有足够的目标时点快照，当前实战候选不会因为 `unavailable` 被保留为可记录候选；只有通过 selected robustness rule 的候选会进入返回列表。live snapshot 缺少多时点上下文时仍走原 live fallback，不做 historical robustness 硬过滤。

## Latest / T-15 / Robust Discovery 对齐报告

本轮额外增加了一个独立研究命令，用来对比三种发现口径：

1. `latest`：每个盘口使用开赛前最新的 oddspapi historical 快照。
2. `T-15 primary`：每个盘口使用 T-15、容忍 `+/-5` 分钟的快照。
3. `robust kept`：基于 T-15 primary 候选，再套用当前 selected robustness rules 后保留下来的候选。

命令：

```powershell
python -m icewine_prediction.cli samples baseline-paper-discovery-alignment `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-paper-discovery-alignment.md `
  --targets 25,20,15,10,5 `
  --primary-target 15 `
  --tolerance-minutes 5 `
  --source-name oddspapi `
  --bookmaker pinnacle
```

本地实际结果摘要：

| Strategy | Latest ROI | T-15 ROI | Latest-only ROI | T15-only ROI | Robust kept ROI | Robust kept not latest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `asian_away_cover_hgb_edge_v1` | 0.0174 | 0.0558 | -0.0519 | 0.0216 | 0.2929 | 5 / 0.4394 |
| `asian_away_cover_hgb_bucket_v2` | 0.0364 | 0.0086 | -0.0297 | -0.1001 | 0.2170 | 11 / -0.1205 |
| `asian_home_cover_hgb_favorite_bucket_v1` | 0.0223 | 0.0911 | -0.0951 | -0.0773 | 0.2402 | 2 / -1.0000 |
| `total_goals_hgb_bucket_v2` | 0.0508 | 0.0263 | 0.0953 | 0.0932 | 0.2231 | 9 / 0.5402 |
| `total_goals_hgb_low_line_bucket_v3` | -0.0630 | -0.1160 | -0.0136 | -0.1288 | 0.1209 | 6 / 0.1607 |
| `total_goals_hgb_confirmed_under_mid_275_v1` | -0.0265 | 0.0119 | 0.0736 | 0.2104 | 0.0119 | 5 / 0.2104 |

解读注意：

- `latest 已经消失但 T-15 还存在` 不应被命名为 stale / 过时信号。这几分钟内的 odds 更新可能是真变化，也可能是假信号或噪声，当前数据不能预设哪一边天然更好。
- 这份报告的目的不是证明 latest 或 T-15 谁更优，而是暴露不同 discovery 口径会切出不同候选池。
- 当前最需要统一的是：未开赛候选生成、训练 / 回测发现候选、finished 历史回填发现候选，三者应尽量走同一个 discovery engine。

## 已实现：第一版多时点联合 Discovery Engine

第一版已实现为多时点 union discovery + 统一鲁棒过滤。当前采用更克制的二元保留策略：

1. 不再把 `latest historical` 当作唯一发现入口。
2. 对同一场比赛构造标准快照组：`T-25 / T-20 / T-15 / T-10 / T-5 / latest`。
3. 每个时点都跑同一套 scorer 和 `paper_strategy_registry.py` 中的 strategy rules。
4. 按 `match_id + strategy_key + market_type + side` 聚合成一个候选观察组。
5. 候选发现采用 multi-timepoint union：任一标准时点命中即可进入观察候选池。
6. 第一版暂不引入 `robust / timing_divergent / weak / rejected` 分层。
7. 正式推荐链路和 finished 历史回填都只返回通过 selected robustness rule 的候选。
8. 未通过规则的候选不返回为候选行，只计入简单舍弃比赛数诊断。
9. 后续如需研究 `timing_divergent` 等分层，应另行回测后再接入。

验收重点：

- scheduled 未开赛页面、finished 历史回填、研究报告对同一场比赛使用同一套 discovery 结果。
- 第一版页面/API 只返回通过规则的候选；`latest-only`、`T15-only`、`robust kept not latest` 仍主要通过研究报告追踪。
- 不能把 `T-15 命中但 latest 不命中` 自动命名为过时或低质量；只能标记为 `timing_divergent`，再由回测决定是否降权。
- 当前 `baseline_paper_discovery_alignment_service.py` 可以作为验收基线：新 discovery engine 落地后，应能复现或解释该报告里的集合拆分差异。

## API 字段

`build_paper_recommendation_queue_payload` 和 `build_paper_tracking_workspace_payload` 均新增：

- `odds_source`
- `execution_target`
- `historical_snapshot_count`
- `robustness_mode`
- `robustness_status`
- `robustness_primary_target`
- `robustness_seen_count`
- `robustness_min_edge`
- `robustness_observed_targets`
- `discarded_by_robustness_match_count`

前端类型位于 `web/src/types.ts` 的 `PaperCandidate`。

## 与多信号复合评分的关系

另一位开发者提交的多信号复合评分逻辑主要在：

`src/icewine_prediction/paper_confidence_service.py`

这套评分是基于已经创建的 `PaperRecommendationRecord` 记录计算的：

1. 按 `match_id + market_type + side` 聚合同场同方向记录。
2. 根据 edge、策略 family、bucket 策略、model consensus、人工调整等因素计算 `confidence_score`。
3. 再映射到 `suggested_stake_units`。

本轮 robust 过滤发生在候选记录前：

- scheduled 和 finished 中不鲁棒的候选都不会进入可记录候选。
- finished 历史回填现在用于模拟真实未开赛操作，而不是保留 filtered 样本做候选展示。

当前没有把 robust 状态直接纳入 `confidence_score`。如果后续要加，建议单独设计并回测。

## 验收 Checklist

- [ ] 运行某个 scheduled 未开赛窗口，确认不通过规则的候选不返回为候选行。
- [ ] 运行某个 finished 历史窗口，确认不通过规则的候选同样不返回为候选行。
- [ ] 确认 `discarded_by_robustness_match_count` 会统计发现过候选但最终被舍弃的比赛数。
- [ ] 在保留候选中检查 `robustness_status == "kept"`、`robustness_seen_count`、`robustness_min_edge`、`robustness_observed_targets`。
- [ ] 确认 `total_goals_hgb_confirmed_under_mid_275_v1` 为 filter，和其他策略使用同样舍弃规则。
- [ ] 确认 confidence/stake 评分仍基于 paper records，而不是 queue rows。
- [ ] 确认批量记录接口仍只记录 `status == "candidate"` 的候选。

## 建议验收命令

生成 raw / kept / filtered 报告：

```powershell
python -m icewine_prediction.cli samples baseline-execution-robustness-filter `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-execution-robustness-filter.md `
  --targets 25,20,15,10,5 `
  --tolerance-minutes 5 `
  --source-name oddspapi `
  --bookmaker pinnacle
```

后端验证：

```powershell
python -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py tests/test_baseline_execution_robustness_filter_service.py -q
```

更完整的相关验证：

```powershell
python -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py tests/test_baseline_execution_robustness_filter_service.py tests/test_baseline_execution_robustness_grid_service.py tests/test_baseline_execution_robustness_service.py tests/test_samples_cli.py -q
```

前端验证：

```powershell
npm test
npm run build
```

## 本轮已验证

最近一次验证结果：

- `python -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py tests/test_paper_recommendation_tracking_service.py tests/test_baseline_execution_robustness_filter_service.py -q`：86 passed
- `npm test`：57 passed
- `npm run build`：成功

上一轮完整相关验证也通过：

- `python -m pytest tests/test_paper_recommendation_queue_service.py tests/test_web_console_api.py tests/test_baseline_execution_robustness_filter_service.py tests/test_baseline_execution_robustness_grid_service.py tests/test_baseline_execution_robustness_service.py tests/test_samples_cli.py -q`：135 passed

## 已知边界

1. `docs/模型实验/` 下报告文件受 `.gitignore` 影响，通常不会进入提交。
2. 前端目前只是类型承接 robustness 字段，尚未做专门 UI 展示。
3. `confirmed_under_mid_275` 当前已改为 filter；如新口径表现不佳，后续可单独重跑并考虑移除。
4. 当前 robust 过滤只作用于 oddspapi historical 快照链路；live snapshot 缺多时点上下文时不会被硬过滤。
5. finished 历史窗口现在和 scheduled 使用同一保留策略，用于模拟真实未开赛操作。

## 建议下一步

1. 在纸面推荐页面展示 robustness 状态、seen count、min edge、observed targets，以及简单舍弃比赛数。
2. 用 5.30 全天 finished 历史窗口验收：返回候选是否等同真实未开赛操作，舍弃比赛数是否合理。
3. 2026-06-04 已按新生成候选口径单独重跑 `total_goals_hgb_confirmed_under_mid_275_v1`；保留样本收益弱于过滤样本，且正收益网格样本过薄，已从策略注册、默认鲁棒规则和候选生成链路移除。
4. 再决定是否将 robustness 结果纳入 `paper_confidence_service.py` 的 confidence score 或 stake cap。

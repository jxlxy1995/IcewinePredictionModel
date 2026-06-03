# 纸面推荐鲁棒过滤器接入交接

## 背景

这轮工作围绕纸面推荐候选的赔率时点误差展开。之前的纸面策略主要基于单一赔率口径生成候选；实战中更接近的使用方式是赛前某个时间点拉取 oddspapi 历史赔率快照，并希望候选在 T-25/T-20/T-15/T-10/T-5 这些相邻执行时点上具有一定稳定性。

本轮目标不是重做模型，也不是改变多信号复合评分机制，而是在纸面推荐候选进入记录前增加一层可验证的鲁棒性基建。

## 本轮目标

1. 回测现有 6 个纸面信号在 raw / kept / filtered 三组下的表现。
2. 将 selected robust 规则抽成共享模块，避免报告和推荐链路规则漂移。
3. 纸面推荐优先使用 scheduled 比赛的 oddspapi historical 快照。
4. 未开赛比赛硬过滤不鲁棒候选。
5. 已完赛历史窗口只标记鲁棒结果，不移除候选，方便验收和回放。
6. API 和前端类型透出 robustness 诊断字段。

## 推荐阅读顺序

1. `src/icewine_prediction/execution_robustness_rules.py`
2. `src/icewine_prediction/baseline_execution_robustness_filter_service.py`
3. `src/icewine_prediction/baseline_execution_robustness_service.py`
4. `src/icewine_prediction/baseline_execution_robustness_grid_service.py`
5. `src/icewine_prediction/paper_recommendation_queue_service.py`
6. `src/icewine_prediction/web_api.py`
7. `web/src/types.ts`
8. `tests/test_baseline_execution_robustness_filter_service.py`
9. `tests/test_paper_recommendation_queue_service.py`
10. `tests/test_web_console_api.py`

## Selected Robust 规则

| Strategy | Mode | Primary | Seen >= | Min edge | Side | Bucket | Line |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `asian_away_cover_hgb_edge_v1` | filter | T-15 | 5 | 0.0800 | stable | stable | any |
| `asian_away_cover_hgb_bucket_v2` | filter | T-15 | 4 | 0.1200 | stable | stable | any |
| `asian_home_cover_hgb_favorite_bucket_v1` | filter | T-15 | 4 | 0.0800 | stable | stable | any |
| `total_goals_hgb_bucket_v2` | filter | T-15 | 2 | 0.1200 | stable | any | any |
| `total_goals_hgb_low_line_bucket_v3` | filter | T-15 | 3 | 0.1200 | stable | any | any |
| `total_goals_hgb_confirmed_under_mid_275_v1` | observe | T-15 | 3 | 0.1200 | stable | any | any |

`observe` 表示只计算并暴露鲁棒性诊断，不硬过滤。当前 `confirmed_under_mid_275` 样本较薄，所以先保持 observe。

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

### Scheduled 未开赛比赛

当比赛是 `scheduled` 且有可用 oddspapi historical 快照时：

1. 先用 latest historical 快照构造 feature row。
2. 按已有 6 个纸面策略生成候选。
3. 对 `status == "candidate"` 的候选，在 T-25/T-20/T-15/T-10/T-5 窗口重跑同一 scorer。
4. 如果 selected robust 规则不通过，状态改为 `robustness_filtered`。
5. `robustness_filtered` 不进入可记录候选列表。

### Finished 已完赛历史窗口

当比赛是 `finished` 时：

1. 仍然计算 robustness 诊断。
2. 如果规则不通过，候选保持 `status == "candidate"`。
3. 追加风险标签 `robustness:filtered`。
4. API 返回 `robustness_status == "filtered"` 等字段。

这样做是为了历史验收时不丢样本。另一位开发者可以直接跑某一天历史比赛，看候选中哪些会在实战 scheduled 链路被硬过滤。

### Unavailable

如果没有足够的目标时点快照，候选保留，并标记：

- `robustness_status == "unavailable"`
- `risk_tags` 追加 `robustness:unavailable`

### Observe

`total_goals_hgb_confirmed_under_mid_275_v1` 目前是 observe：

- 不硬过滤。
- 返回 robustness 字段。
- 作为后续样本积累和规则再验证的观察项。

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

前端类型位于 `web/src/types.ts` 的 `PaperCandidate`。

## 与多信号复合评分的关系

另一位开发者提交的多信号复合评分逻辑主要在：

`src/icewine_prediction/paper_confidence_service.py`

这套评分是基于已经创建的 `PaperRecommendationRecord` 记录计算的：

1. 按 `match_id + market_type + side` 聚合同场同方向记录。
2. 根据 edge、策略 family、bucket 策略、model consensus、人工调整等因素计算 `confidence_score`。
3. 再映射到 `suggested_stake_units`。

本轮 robust 过滤发生在候选记录前：

- scheduled 中不鲁棒的候选不会进入可记录候选。
- finished 中不鲁棒的候选会保留并标记，方便历史验收。

当前没有把 robust 状态直接纳入 `confidence_score`。如果后续要加，建议单独设计并回测。

## 验收 Checklist

- [ ] 运行某个 scheduled 未开赛窗口，确认不通过规则的候选状态为 `robustness_filtered`。
- [ ] 确认 `robustness_filtered` 不出现在可记录候选列表中。
- [ ] 运行某个 finished 历史窗口，确认候选仍保留为 `candidate`。
- [ ] 在 finished 候选中检查 `robustness_status`、`robustness_seen_count`、`robustness_min_edge`、`robustness_observed_targets`。
- [ ] 确认 finished 中不通过规则的候选带 `risk_tags: robustness:filtered`。
- [ ] 确认 `total_goals_hgb_confirmed_under_mid_275_v1` 为 observe，不硬过滤。
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
3. `confirmed_under_mid_275` 当前样本太少，暂不硬过滤。
4. 当前 robust 过滤只作用于 oddspapi historical 快照链路；live snapshot 缺多时点上下文时不会被硬过滤。
5. finished 历史窗口只标记不过滤，是为了方便验证过滤器工作效能。

## 建议下一步

1. 在纸面推荐页面展示 robustness 状态、seen count、min edge、observed targets。
2. 用 5.30 全天 finished 历史窗口验收：候选是否保留、robustness 字段是否正常。
3. 对比 finished 候选中 `robustness_status == "kept"` 与 `filtered` 的实际收益。
4. 再决定是否将 robustness 结果纳入 `paper_confidence_service.py` 的 confidence score 或 stake cap。

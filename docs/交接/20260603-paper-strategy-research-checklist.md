# 纸面策略研发与鲁棒过滤 Checklist

## 目的

新增纸面策略或把研究信号推进到实战推荐前，不能只看 raw ROI。实战执行时赔率抓取时点会有误差，因此必须验证候选在相邻执行时点上的稳定性。

本 checklist 适用于：

- 新增 `paper_strategy_registry.py` 中的 `PaperStrategy`
- 调整已有纸面策略阈值
- 从模型实验报告中提拔新信号
- 将候选纳入 scheduled 纸面推荐实战链路

## 必看指标

每个候选策略至少需要比较以下四组：

1. Raw 表现：原始 close/live 或当前研究口径下的候选数、ROI、hit rate。
2. T-15 表现：使用 T-15 赔率口径重跑后的候选数、ROI、hit rate。
3. Robust kept 表现：通过 selected robust 规则保留下来的候选数、ROI、hit rate。
4. Robust filtered 表现：被 robust 规则过滤掉的候选数、ROI、hit rate。

如果 kept 组没有优于 raw，或 filtered 组不差甚至更好，不能直接进入实战推荐，应回到策略设计或阈值选择阶段。

## 推荐命令

先比较 close/live 与 T-15 口径：

```powershell
python -m icewine_prediction.cli samples baseline-t15-signal-comparison `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-t15-signal-comparison.md `
  --source-name oddspapi `
  --bookmaker pinnacle `
  --target-minutes 15 `
  --tolerance-minutes 5
```

再看多时点鲁棒分层：

```powershell
python -m icewine_prediction.cli samples baseline-execution-robustness `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-execution-robustness.md `
  --targets 25,20,15,10,5 `
  --primary-target 15 `
  --tolerance-minutes 5 `
  --source-name oddspapi `
  --bookmaker pinnacle
```

扫描 candidate 规则网格：

```powershell
python -m icewine_prediction.cli samples baseline-execution-robustness-grid `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-execution-robustness-grid.md `
  --targets 25,20,15,10,5 `
  --primary-targets 15,10 `
  --tolerance-minutes 5 `
  --source-name oddspapi `
  --bookmaker pinnacle `
  --min-candidate-count 10 `
  --top-n-per-strategy 5
```

最终验收 raw / kept / filtered：

```powershell
python -m icewine_prediction.cli samples baseline-execution-robustness-filter `
  --csv-path local_data/training/baseline_dynamic_features_main_leagues_20260601-1451.csv `
  --report-path docs/模型实验/20260603-baseline-execution-robustness-filter.md `
  --targets 25,20,15,10,5 `
  --tolerance-minutes 5 `
  --source-name oddspapi `
  --bookmaker pinnacle
```

## 提拔新策略前的 Checklist

- [ ] `paper_strategy_registry.py` 中的 strategy key、market type、side、edge threshold 明确。
- [ ] Raw 组候选数、ROI、hit rate 已记录。
- [ ] T-15 组候选数、ROI、hit rate 已记录。
- [ ] Robust kept 组候选数、ROI、hit rate 已记录。
- [ ] Robust filtered 组候选数、ROI、hit rate 已记录。
- [ ] Kept 组表现明显优于 raw 或更符合实战风险偏好。
- [ ] Filtered 组没有表现出比 kept 更好的反证。
- [ ] 样本数足够支撑 filter；样本太少时先设为 observe。
- [ ] `src/icewine_prediction/execution_robustness_rules.py` 中新增或调整 selected rule。
- [ ] scheduled 推荐链路验证：不通过 filter 的候选不会进入可记录候选。
- [ ] finished 历史窗口验证：不通过 filter 的候选仍保留，但带 `robustness_status` 和 `robustness:filtered`。
- [ ] 多信号复合评分仍在 `paper_confidence_service.py` 中基于 paper records 计算；如需把 robustness 纳入评分，另行回测。

## 当前约定

- `scheduled` 未开赛推荐：filter 模式会硬过滤不鲁棒候选。
- `finished` 历史回放：只标记不硬过滤，方便验收效果。
- `observe` 模式：只标记不硬过滤，适合样本不足的新信号。
- live snapshot 缺少多时点上下文时，不应因为 robustness 不可用而直接误杀候选。

## 相关文件

- `src/icewine_prediction/paper_strategy_registry.py`
- `src/icewine_prediction/execution_robustness_rules.py`
- `src/icewine_prediction/baseline_t15_signal_comparison_service.py`
- `src/icewine_prediction/baseline_execution_robustness_service.py`
- `src/icewine_prediction/baseline_execution_robustness_grid_service.py`
- `src/icewine_prediction/baseline_execution_robustness_filter_service.py`
- `src/icewine_prediction/paper_recommendation_queue_service.py`
- `docs/交接/20260603-paper-robustness-handoff.md`

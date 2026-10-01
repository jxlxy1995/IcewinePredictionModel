# 2026-10-01 Bark 纸面观察过滤规则

## 已批准并启用的行为

本次根据9月回顾及用户确认，仅调整自动任务的 Bark 展示。以下五项同时满足的推荐组不再发送推荐明细：

- 亚盘（`asian_handicap`）。
- 主队方向（`home_cover`）。
- 快照冻结建议手数为 `1.50`。
- 组内恰好一条信号记录。
- 快照冻结盘口为 `-0.50`，即主队让0.50球。

另外，冻结建议手数为 `0.00` 的推荐组也隐藏，不限市场、方向、盘口或信号数量。两类规则共用开关。

按每批实际命中原因显示以下一句：

| 命中情况 | Bark 提示 |
| --- | --- |
| 仅原观察规则 | 本批已隐藏：仅纸面观察信号。 |
| 仅0手规则 | 本批已隐藏：0手推荐。 |
| 两类都有 | 本批已隐藏：仅纸面观察信号、0手推荐。 |

不标出场次或数量。其他推荐组照常展示，同一场的其他方向或市场不连带过滤。整批全部命中时，正文只有对应提示。长批次拆成多条消息时，提示在整批中只出现一次。没有命中则不显示提示。标题仍显示原有已记录条数。

全部纸面信号记录和分组快照先正常保存，再过滤通知。冻结手数、后续结算和回顾统计照旧；模型、策略、评分、手数、stake cap、联赛准入均未调整。不要将历史回顾重新计算为“已过滤”的策略收益。

## 开关与审计

`config/paper_automation.yaml` 新增 `bark_observation_filter_enabled: true`。改为 `false` 即关闭通知过滤，后续任务恢复全部推荐明细；开关在每次执行自动任务时读取。缺少配置文件或该键时默认关闭，值必须为 YAML 布尔值。

任务结果 `result_payload.bark.observation_filter` 保留：

- `enabled`：本批开关状态。
- `rule_id`：`home_minus_050_single_stake_150_v1`。
- `snapshot_ids`、`group_keys`：本批命中组，用于后续只读复盘。

新增 `result_payload.bark.zero_stake_filter`，字段相同，`rule_id` 为 `zero_stake_v1`，仅记录0手规则命中组。两类审计分开，原有完整记录ID、快照ID和组列表继续保留。审计明细不出现在手机提示中。

## 首轮观察规则验证与生效

- 相关自动任务、调度、快照测试：89项通过。覆盖严格五条件、开关关闭、整批过滤、混合批次、同场其他组保留、分条通知，以及被过滤记录仍能正常结算且冻结1.50手不变。
- 全量测试：950项通过、13项失败。将本次修改的两个生产模块在独立临时副本恢复为 HEAD 后，同样13项失败全部复现。失败集中于历史赔率时间点/供应商优先级、SBOBet回退、纸面候选时间点与稳健性、Web默认赔率同步开关；未在本次扩大修复范围。
- 真实9月 automation 快照只读回放：834组中命中23组，冻结34.50手、weighted profit -7.450，其余811组保留；提示句整批恰好一次。通过 SQLite `mode=ro` 和 `query_only=ON` 查询，使用冻结快照构造组，未重算手数、未写库、未发测试 Bark。
- 独立代码审查未发现实质性问题；相关改动 `git diff --check` 通过。
- 北京时间2026-10-01 15:37完成统一 Web 服务重启，后端新进程 PID 27092、前端 PID 14596；`GET /api/health` 返回 `{"status":"ok"}`，前端 HTTP 200。重启前后均无运行中或待执行纸面自动任务，配置开关为 true。
- 普通沙箱因系统进程查询权限不足无法可靠执行重启，随后使用获准的系统权限执行成功。没有主动发送真实 Bark 测试消息；下一批真实自动任务将使用本规则。

## 第二轮0手过滤验证

- 用户明确批准增加0手过滤、区分两类简短提示，并要求提交本轮修改。
- 先增加失败测试，再实现过滤；99项相关测试通过。覆盖两类单独/同时命中、长消息分条、全部过滤、同场可见组、关闭开关、0手纸面记录与快照完整保存，以及0手记录正常结算后仍保留冻结0手。
- 真实9月 automation 快照只读回放：834组中原规则命中23组、0手规则命中93组，两类互斥，剩余718组。消息中没有0手推荐明细，两类合并提示恰好一次；未发送真实 Bark、未写库。
- 独立代码审查未发现实质性问题。
- 北京时间2026-10-01 16:10已完成服务重启并加载第二轮规则，后端 PID 34424、前端 PID 6484；健康接口为 `ok`、前端 HTTP 200，过滤开关为 true，重启前后无运行中或待执行自动任务。本轮没有发送真实 Bark 测试消息。
- 全量测试：960项通过、13项既有失败，与首轮完全相同，没有新增失败。失败测试名如下，均在 `tests/` 下：

```text
test_historical_odds_service.py::test_supplement_execution_timepoint_snapshots_uses_strict_five_minute_tolerance
test_historical_training_sample_service.py::test_historical_training_samples_can_use_pinnacle_provider_priority
test_historical_training_sample_service.py::test_historical_training_samples_provider_priority_falls_back_to_sbobet
test_match_list_workspace_service.py::test_match_list_workspace_uses_sbobet_when_pinnacle_is_missing
test_match_list_workspace_service.py::test_match_detail_execution_timepoint_coverage_reports_sbobet_bookmaker
test_oddspapi_sync_runner.py::test_run_oddspapi_sync_for_session_preserves_execution_timepoints_after_sampling
test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_replays_finished_match_with_sbobet_historical_odds
test_paper_recommendation_queue_service.py::test_paper_queue_prefers_the_odds_api_pinnacle_snapshots_over_oddspapi
test_paper_recommendation_queue_service.py::test_paper_queue_uses_sbobet_when_pinnacle_is_missing
test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_falls_back_to_t30_for_t10_decision_price
test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_does_not_use_t5_or_latest_for_t10_robustness
test_paper_recommendation_queue_service.py::test_build_paper_recommendation_queue_applies_robustness_to_distribution_confirmed_candidates
test_web_console_api.py::test_web_console_api_default_odds_syncer_uses_match_odds_sync_service
```

## 后续回顾

从启用时点向前跟踪过滤组，分别查看纸面全量、通知可见组与仅纸面观察组。半个月或一个月后按固定规则复核样本数、冻结暴露及收益；9月23组属于选择规则所依据的历史样本，不能作为规则有效性的独立验证。

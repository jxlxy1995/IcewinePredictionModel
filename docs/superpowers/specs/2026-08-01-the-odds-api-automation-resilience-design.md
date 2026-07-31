# The Odds API 自动任务韧性设计

## 背景

纸面自动任务会在同一开赛时间包含多场比赛，并将全部比赛一次性交给统一赔率同步服务。当前 The Odds API 请求没有显式节流或重试；runner 遇到一个请求异常后会停止整个赛季批次，上层又会把同一个批次错误复制给所有没有可信赔率的比赛。

自动任务 `337` 暴露了这一问题：同步共发起 7 次请求，其中一个请求发生 `ReadTimeout`，runner 随即停止。任务结果最终显示 3 场失败，但这不是 3 次独立请求失败。相关比赛在北京时间 2026-08-01 08:53 至 08:54 手动刷新成功，说明错误具有瞬时性，但现有日志不足以判断是否由请求突发、网络抖动或供应商响应变慢引起。

## 目标

- The Odds API 请求之间保持可配置的最小启动间隔。
- 对明确的瞬时错误执行有上限的重试。
- 单场或单个共享请求失败时继续处理其他比赛。
- 自动任务新增耗时最多 120 秒。
- 准确区分实际失败、未尝试、旧赔率兜底和重试恢复。
- 保存足够且不泄露凭证的诊断日志。
- 保持现有自动任务表、Web 调用方式和主要返回字段兼容。

## 非目标

- 不修改 Oddspapi、zqcf918 的请求策略。
- 不新增延迟补偿任务或新的调度队列。
- 不改变开赛前 9 分钟的自动任务触发规则。
- 不改变推荐生成、赔率时间点选择或可信赔率优先级。
- 不调用真实 The Odds API 作为自动测试的一部分。

## 当前调用链

```text
PaperAutomationScheduler
  -> execute_paper_automation_task
  -> match_list_odds_syncer(match_ids)
  -> run_match_odds_sync_for_session
  -> run_the_odds_api_sync_for_session
  -> TheOddsApiClient.get
```

当前 runner 按开赛时间和比赛 ID 处理比赛。每场比赛会请求已经到达的标准执行时间点，当前标准时间点为 `T-60/T-30/T-25/T-20/T-15/T-10`。同一 `sport_key + 时间点` 的历史响应会在单次同步内复用。

## 设计概览

设计分为三层：

1. `TheOddsApiClient` 负责进程级节流、HTTP 错误分类、单次请求重试和请求日志。
2. `the_odds_api_sync_runner` 负责同步级时间预算、共享请求缓存、逐场错误隔离和逐场诊断结果。
3. `match_odds_sync_service` 负责主源与 fallback 的最终状态合并，向自动任务返回兼容且准确的结果。

自动任务和 Web 手动赔率刷新使用相同的进程级 limiter。在同一 Web 进程内，两类请求不会绕过彼此的最小请求间隔。本设计不承诺跨进程限速；如果未来并行运行多个 Web/worker 进程，需要改为跨进程协调器。

## 请求节流

新增 The Odds API 专用的线程安全请求 limiter，沿用项目中已有的单调时钟与锁模式，但不依赖 Oddspapi 模块。

默认参数：

```text
request_cooldown_seconds = 1.0
```

规则：

- limiter 控制相邻请求尝试的启动时间，首次请求和重试都必须经过 limiter。
- limiter 使用 `time.monotonic()`，避免系统时间调整影响间隔。
- limiter 在锁内计算剩余等待并登记新的请求启动时间，保证同一进程的并发调用串行通过。
- limiter 的等待方法接收当前调用允许消耗的最大等待预算；检查、等待和登记必须在同一个临界区完成，避免并发请求在预算检查后插队。
- 网络请求本身超过 1 秒时，不再额外等待已经自然消耗的时间。
- 自动任务和手动刷新创建的客户端共享同一个进程级 limiter。

## 错误分类与重试

单个请求最多执行两次：首次请求加一次重试。

| 错误类型 | 是否重试 | 默认退避 |
|---|---:|---:|
| `ReadTimeout`、连接错误 | 是 | 5 秒 |
| HTTP 429 | 是 | `Retry-After`，缺失时 15 秒 |
| HTTP 500/502/503/504 | 是 | 5 秒 |
| HTTP 401/403 | 否 | 0 秒 |
| 其他 4xx、参数错误 | 否 | 0 秒 |
| 本地请求额度耗尽 | 否 | 0 秒 |
| 无法匹配比赛、没有可用盘口 | 否 | 交给现有 fallback |

`Retry-After` 只接受非负秒数；无法解析时使用 15 秒。退避等待和 limiter 等待取较晚的可请求时间，不重复累计两段 sleep。

重试请求仍计入 `request_count` 和供应商额度统计。超过现有本地 request budget 时不得重试。

## 120 秒额外时间预算

每次 `run_match_odds_sync_for_session` 创建独立的额外时间预算，默认上限为 120 秒，并把同一个预算对象传给该次同步涉及的所有赛季 runner。预算不能在赛季切换时重置。直接调用 `run_the_odds_api_sync_for_session` 且没有传入预算时，由 runner 创建相同默认预算，保持 CLI 和测试调用行为完整。

预算只统计相对当前行为新增的耗时：

- limiter 实际等待时间；
- 错误退避实际等待时间；
- 重试请求的实际执行时间。

首次请求的网络执行时间属于原有行为，不计入额外预算。

发起重试前必须保守预留：

```text
合并后的等待时间 + 单次请求 timeout_seconds
```

剩余预算无法覆盖该上限时，跳过重试并将当前请求标记为 `retry_budget_exhausted`。重试完成后按实际等待和实际请求耗时扣减预算，不按预留上限扣减。

首次请求也必须遵守 limiter。如果剩余额外预算无法覆盖下一次首次请求需要的 limiter 等待，则不能绕过限速；当前及剩余未执行比赛标记为 `not_attempted`，原因为 `extra_time_budget_exhausted`。这保证任务不会为了赶时间重新形成请求突发。

返回结果包含：

```text
recovery_elapsed_seconds
recovery_budget_remaining_seconds
rate_limit_wait_seconds
retry_count
retry_success_count
```

## 共享请求缓存

保留当前按以下键复用历史响应的行为：

```text
(sport_key, snapshot_time, region, bookmaker, markets)
```

缓存值扩展为成功或失败两种明确结果：

- 成功响应只请求一次，供所有依赖比赛复用。
- 瞬时错误重试后仍失败时，缓存规范化错误、尝试次数和耗时。
- 后续依赖相同键的比赛复用失败结果，不对同一 endpoint 重复轰击。
- 不同 sport key 或不同时间点互相隔离。

一个历史时间点失败时，继续请求该比赛的其他时间点。如果其他时间点已经得到可用赔率，则保存可用快照，并将主源刷新状态标记为 `partial_success`。只有没有任何可用快照且当前赔率补充也失败时，该比赛才视为主源刷新失败。

## 比赛级错误隔离

runner 不再在第一个 `TheOddsApiApiError` 或请求预算错误后直接 `break` 整批。它维护逐场结果：

```text
match_results
match_errors
not_attempted_match_ids
```

处理规则：

1. 当前比赛成功时保存快照并继续下一场。
2. 当前比赛部分时间点成功时保存可用快照，记录 `partial_success` 并继续。
3. 当前比赛主源最终失败时记录该比赛的真实错误并继续。
4. 只有数据库会话失效、配置缺失等无法继续的批次级错误才终止整个 runner。
5. 批次级错误必须明确返回实际已处理和未尝试的比赛，不能把错误复制成每场独立请求失败。

## 主源与 fallback 合并

`match_odds_sync_service` 根据逐场主源结果和最终可信赔率状态生成输出：

- 主源刷新成功：放入 `success`，`primary_refresh_status=success`。
- 主源部分成功且有可用快照：放入 `success`，`primary_refresh_status=partial_success`。
- 主源失败、fallback 成功：放入 `success`，`primary_refresh_status=failed_fallback_used`，保留主源错误。
- 主源失败、已有可信旧赔率：放入 `success`，`primary_refresh_status=failed_existing_odds_used`，保留主源错误。
- 主源和 fallback 均失败且没有可信赔率：放入 `failed`，`failure_stage=fallback`。
- 因时间或请求预算没有发起必要请求：放入 `not_attempted`。

`fallback_failed` 作为 `failed` 项目的语义子类型，通过 `failure_stage` 和 `fallback_error` 表达，不另建重复列表，避免同一比赛被重复计数。

## 返回结果

保留现有顶层字段：

```json
{
  "success": [],
  "failed": [],
  "skipped": [],
  "requests": 0,
  "credits": 0
}
```

新增字段：

```json
{
  "not_attempted": [],
  "trace_id": "sync trace id",
  "retry_count": 0,
  "retry_success_count": 0,
  "rate_limit_wait_seconds": 0.0,
  "recovery_elapsed_seconds": 0.0,
  "recovery_budget_remaining_seconds": 120.0,
  "odds_status": "success"
}
```

`odds_status` 取值：

- `success`：全部目标比赛获得可用赔率或被明确跳过。
- `partial`：至少一场成功，同时存在最终失败或未尝试。
- `failed`：没有目标比赛获得可用赔率，并存在最终失败或未尝试。

成功项示例：

```json
{
  "match_id": 14083,
  "message": "赔率已刷新",
  "source": "the_odds_api",
  "attempt_count": 2,
  "retried": true,
  "primary_refresh_status": "success",
  "primary_refresh_error": null
}
```

失败项示例：

```json
{
  "match_id": 14083,
  "message": "The Odds API request failed: ReadTimeout",
  "error_code": "read_timeout",
  "failure_stage": "fallback",
  "attempt_count": 2,
  "retry_exhausted": true,
  "fallback_error": "missing zqcf918 match ID"
}
```

## 追踪与日志

每次统一赔率同步生成一个不含业务秘密的 `trace_id`，传递给 runner 和 client，并返回给调用方。自动任务会自然地把该值保存到现有 `result_payload`，不需要增加数据库字段。

runner 记录：

- `trace_id`、match ID、sport key；
- 比赛开始、完成和最终状态；
- 使用了哪些历史时间点；
- 共享缓存命中、共享失败复用；
- fallback 状态和额外预算摘要。

client 记录：

- endpoint 类别和经过白名单筛选的参数；
- 请求序号、尝试次数、开始和结束时间；
- 请求耗时、HTTP 状态或规范化错误码；
- limiter 等待、退避等待、剩余预算。

不得记录：

- API Key；
- 包含 API Key 的完整 URL；
- Authorization/Cookie 等请求头；
- 未筛选的响应原文。

日志异常文本继续使用现有脱敏原则，不能直接拼接可能包含查询参数的底层异常 URL。

## 自动任务通知

任务只要完整执行完赔率同步、候选生成和通知流程，现有 `PaperAutomationTask.status` 仍为 `success`。赔率层的部分失败由 `odds_status=partial` 表达，不修改任务表结构。

Bark 摘要增加：

```text
赔率刷新：成功2 失败1 未尝试0
重试：1次，恢复1场
旧赔率兜底：1场
额外耗时：46秒
```

通知只展示汇总，不逐条发送请求错误。完整诊断保存在任务 `result_payload` 和服务日志中。

## 测试设计

测试全部使用 fake client、可控单调时钟和 fake sleep，不访问真实 The Odds API。

### Client 与 limiter

- 连续首次请求的启动间隔至少为 1 秒。
- 首次请求和重试共用 limiter。
- 两个客户端共享进程级 limiter，覆盖自动和手动并发场景。
- `ReadTimeout`、连接错误、429、500/502/503/504 各重试一次。
- 其他 4xx、鉴权错误和本地额度耗尽不重试。
- 429 优先采用合法 `Retry-After`，非法或缺失时等待 15 秒。
- 请求数、额度、等待时间和预算扣减准确。
- 任何日志和异常都不包含 API Key。

### Runner 隔离

- 构造 5 场同一开赛时间比赛，前 6 次请求成功，第 7 次 `ReadTimeout`，重试成功；验证后续比赛继续执行。
- 第 7 次请求重试仍失败时，仅依赖该失败请求的比赛携带错误，其他 sport key 继续执行。
- 第一场最终失败后，第二至第五场仍会处理。
- 单个时间点失败但其他时间点可用时保存部分快照并返回 `partial_success`。
- 相同共享请求键只发一次成功请求。
- 相同共享请求键重试耗尽后复用失败，不重复请求。

### 时间预算

- limiter、退避和重试请求耗时均计入额外预算。
- 剩余预算不足以覆盖退避加 40 秒超时时不重试。
- 剩余预算不足以覆盖首次请求的 limiter 等待时，剩余比赛进入 `not_attempted`。
- 所有受控新增耗时不超过 120 秒。

### 服务与自动任务

- 主源成功、部分成功、fallback 成功、旧赔率兜底和最终失败正确合并。
- 一个批次错误不会复制成多场独立请求失败。
- `success`、`failed`、`skipped` 旧字段继续存在。
- `not_attempted`、重试统计和 `odds_status` 正确。
- Bark 汇总计数与任务结果一致。

## 验收标准

- 任意一场或一个共享请求超时不会终止整个正常同步批次。
- 不再出现一个请求异常被记录成多场独立请求失败。
- 正常任务只增加必要的 1 秒请求启动间隔。
- 所有主动等待和重试的新增耗时受 120 秒预算约束。
- 自动任务和手动请求在同一进程共享 limiter。
- 现有 Web 手动同步、自动任务调用方式和主要返回字段保持兼容。
- 日志足以区分 429、读超时、连接错误、5xx、额度耗尽和比赛匹配失败。
- Bark 能区分成功、实际失败、未尝试、重试恢复和旧赔率兜底。
- 聚焦测试和相关自动任务回归测试全部通过。

## 预计修改范围

- `src/icewine_prediction/sources/the_odds_api_client.py`
- `src/icewine_prediction/the_odds_api_sync_runner.py`
- `src/icewine_prediction/match_odds_sync_service.py`
- `src/icewine_prediction/paper_automation_service.py`
- 对应的 client、runner、match sync 和 automation 测试

不需要数据库迁移或前端强制改动。新增返回字段允许前端后续按需展示。
